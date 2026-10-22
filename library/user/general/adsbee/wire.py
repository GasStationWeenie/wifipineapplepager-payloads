"""Small RFC6455 client: no pip packages needed on the Pager."""
import base64
import hashlib
import os
import socket
import struct
import threading
import time

LIMIT = 1024 * 1024


class WebSocket:
    def __init__(self, host, path, port=80):
        self.sock = None
        self.buffer = bytearray()
        self.parts = bytearray()
        self.fragment = None
        self.send_lock = threading.Lock()
        try:
            self.sock = socket.create_connection((host, port), timeout=3)
            key = base64.b64encode(os.urandom(16)).decode()
            request = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                       f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                       f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
            self.sock.sendall(request.encode())
            deadline = time.monotonic() + 5
            while b"\r\n\r\n" not in self.buffer:
                if len(self.buffer) > 16384 or time.monotonic() > deadline:
                    raise OSError("WebSocket handshake too large or too slow")
                data = self.sock.recv(4096)
                if not data:
                    raise OSError("Connection closed during handshake")
                self.buffer.extend(data)
            header, rest = bytes(self.buffer).split(b"\r\n\r\n", 1)
            lines = header.decode("latin1").split("\r\n")
            fields = {name.lower(): value.strip() for name, value in
                      (line.split(":", 1) for line in lines[1:] if ":" in line)}
            accept = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            if (lines[0].split()[1] != "101" or
                    fields.get("sec-websocket-accept", "") != accept or
                    fields.get("upgrade", "").lower() != "websocket" or
                    "upgrade" not in fields.get("connection", "").lower()):
                raise OSError("ADSBee rejected WebSocket upgrade (check IP/firmware)")
            self.buffer = bytearray(rest)
            self.sock.settimeout(0.2)
        except Exception:
            self.close()
            raise

    def send(self, payload, opcode=1):
        if isinstance(payload, str):
            payload = payload.encode()
        if len(payload) > LIMIT:
            raise ValueError("Message too large")
        mask = os.urandom(4)
        n = len(payload)
        header = bytes([0x80 | opcode])
        if n < 126:
            header += bytes([0x80 | n])
        elif n <= 65535:
            header += bytes([0xFE]) + struct.pack("!H", n)
        else:
            header += bytes([0xFF]) + struct.pack("!Q", n)
        body = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        with self.send_lock:
            self.sock.sendall(header + mask + body)

    def _frame(self):
        b = self.buffer
        if len(b) < 2:
            return None
        first, second = b[:2]
        if first & 0x70 or second & 0x80:
            raise OSError("Unsupported WebSocket frame flags")
        n, offset = second & 127, 2
        if n == 126:
            if len(b) < 4:
                return None
            n, offset = struct.unpack("!H", b[2:4])[0], 4
        elif n == 127:
            if len(b) < 10:
                return None
            n, offset = struct.unpack("!Q", b[2:10])[0], 10
        opcode, final = first & 15, bool(first & 128)
        if n > LIMIT or (opcode >= 8 and (not final or n > 125)):
            raise OSError("Invalid or oversized WebSocket frame")
        if len(b) < offset + n:
            return None
        data = bytes(b[offset:offset + n])
        del b[:offset + n]
        return final, opcode, data

    def receive(self):
        """Return bytes for one message, or None after a short idle interval."""
        while True:
            frame = self._frame()
            if frame is None:
                try:
                    data = self.sock.recv(16384)
                except socket.timeout:
                    return None
                if not data:
                    raise OSError("ADSBee disconnected")
                self.buffer.extend(data)
                continue
            final, opcode, data = frame
            if opcode == 8:
                raise OSError("ADSBee closed WebSocket")
            if opcode == 9:
                self.send(data, 10)
                continue
            if opcode == 10:
                continue
            if opcode in (1, 2):
                if self.fragment is not None:
                    raise OSError("Unexpected new fragmented message")
                if final:
                    return data
                self.fragment = opcode
                self.parts = bytearray(data)
            elif opcode == 0 and self.fragment is not None:
                self.parts.extend(data)
                if len(self.parts) > LIMIT:
                    raise OSError("Fragmented message too large")
                if final:
                    result = bytes(self.parts)
                    self.parts.clear()
                    self.fragment = None
                    return result
            else:
                raise OSError("Invalid WebSocket opcode")

    def close(self):
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()


class Feed(threading.Thread):
    """One reconnecting endpoint. Commands are sent once, never queued/replayed."""
    def __init__(self, host, path, callback, port=80):
        super().__init__(daemon=True)
        self.host, self.path, self.callback, self.port = host, path, callback, port
        self.halt = threading.Event()
        self.ws = None
        self.status = "Connecting"
        self.last_rx = None
        self.guard = threading.Lock()

    def run(self):
        delay = 1
        while not self.halt.is_set():
            ws = None
            try:
                self.status = "Connecting"
                ws = WebSocket(self.host, self.path, self.port)
                with self.guard:
                    self.ws = ws
                self.status = "Connected"
                delay = 1
                heartbeat = time.monotonic()
                while not self.halt.is_set():
                    data = ws.receive()
                    if data is not None:
                        self.last_rx = time.monotonic()
                        self.callback(data)
                    if time.monotonic() - heartbeat >= 30:
                        # Same application heartbeat as ADSBee's web UI. Never send to console.
                        ws.send(b"" if self.path == "/console" else "ping",
                                9 if self.path == "/console" else 1)
                        heartbeat = time.monotonic()
            except (OSError, ValueError) as exc:
                self.status = "Retry: " + str(exc)[:85]
            finally:
                with self.guard:
                    self.ws = None
                if ws:
                    ws.close()
            self.halt.wait(delay)
            delay = min(15, delay * 2)

    def command(self, text):
        with self.guard:
            if self.ws is None or self.status != "Connected":
                return False
            try:
                # Matches the web console's binary UTF-8 command framing.
                self.ws.send(text.rstrip("\r\n") + "\r\n", 2)
                return True
            except OSError:
                self.status = "Send failed; command not retried"
                return False

    def stop(self):
        self.halt.set()
        with self.guard:
            if self.ws:
                self.ws.close()
