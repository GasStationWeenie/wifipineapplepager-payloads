"""ADSBee stream state and navigation calculations, independent of the display."""
from collections import deque
import json
import math
import re
import threading
import time


def number(value):
    if isinstance(value, bool):
        return None
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def coordinates(lat, lon):
    lat, lon = number(lat), number(lon)
    return (lat, lon) if lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180 else None


def distance_bearing(center, position):
    lat1, lon1, lat2, lon2 = map(math.radians, (*center, *position))
    dl = (lon2 - lon1 + math.pi) % (2 * math.pi) - math.pi
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dl / 2) ** 2
    distance = 3440.065 * 2 * math.asin(math.sqrt(max(0, min(1, a))))
    bearing = math.degrees(math.atan2(math.sin(dl) * math.cos(lat2),
                                    math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dl))) % 360
    return distance, bearing


def relative(plane, center=None):
    pos = coordinates(plane.get("lat"), plane.get("lon"))
    if center is not None:
        return distance_bearing(center, pos) if pos else None
    distance, bearing = number(plane.get("r_dst")), number(plane.get("r_dir"))
    if distance is not None and distance >= 0 and bearing is not None:
        return distance, bearing % 360
    return None


def clean(value, limit=80):
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in str(value))[:limit]


def flatten(data, prefix=""):
    rows = []
    if isinstance(data, dict):
        for key, value in data.items():
            rows.extend(flatten(value, prefix + ("." if prefix else "") + str(key)))
    elif isinstance(data, list):
        for i, value in enumerate(data[:32]):
            rows.extend(flatten(value, f"{prefix}[{i}]"))
    else:
        rows.append((prefix, clean(data)))
    return rows


class State:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.planes = {}
        self.metrics = {}
        self.metrics_at = None
        self.console = deque(maxlen=500)
        self.partial = ""
        self.ansi_tail = ""
        self.bad_aircraft = 0
        self.bad_metrics = 0

    def aircraft(self, payload):
        try:
            data = json.loads(payload)
            # Current firmware batches arrays; older versions send individual objects.
            rows = data if isinstance(data, list) else data.get("aircraft", [data]) if isinstance(data, dict) else []
            if not isinstance(rows, list):
                raise ValueError("Invalid aircraft envelope")
        except (ValueError, UnicodeError):
            with self.lock:
                self.bad_aircraft += 1
            return
        with self.lock:
            now = self.clock()
            for row in rows[:1000]:
                if not isinstance(row, dict) or not re.fullmatch(r"~?[0-9a-fA-F]{6}", str(row.get("hex", ""))):
                    continue
                key = row["hex"].lower()
                # Each report is a record, not a patch: absent fields may have become invalid.
                record = dict(row, hex=key, received=now)
                age = number(row.get("seen_pos"))
                record["position_at"] = now - max(0, age) if age is not None else now
                self.planes[key] = record
            self._prune(now)
            if len(self.planes) > 1000:
                keep = sorted(self.planes, key=lambda k: self.planes[k]["received"], reverse=True)[:1000]
                self.planes = {k: self.planes[k] for k in keep}

    def _prune(self, now):
        self.planes = {k: p for k, p in self.planes.items() if now - p["received"] <= 60}

    def metric(self, payload):
        try:
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError("Invalid metrics")
        except (ValueError, UnicodeError):
            with self.lock:
                self.bad_metrics += 1
            return
        with self.lock:
            self.metrics.update(data)
            self.metrics_at = self.clock()

    def text(self, payload):
        text = payload.decode("utf8", "replace") if isinstance(payload, bytes) else payload
        with self.lock:
            # Keep split ANSI CSI sequences from leaking into the display.
            text = self.ansi_tail + text
            self.ansi_tail = ""
            match = re.search(r"\x1b(?:\[[0-?]*[ -/]*)?$", text)
            if match:
                self.ansi_tail = match.group()[-64:]
                text = text[:match.start()]
            text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
            for c in text:
                if c == "\n":
                    self.console.append(self.partial)
                    self.partial = ""
                elif c == "\b":
                    self.partial = self.partial[:-1]
                elif c == "\t":
                    self.partial += "    "
                elif c >= " " and c != "\x7f":
                    self.partial += clean(c, 1)
                if len(self.partial) >= 78:
                    self.console.append(self.partial[:78])
                    self.partial = self.partial[78:]

    def snapshot(self):
        with self.lock:
            self._prune(self.clock())
            return (list(self.planes.values()), dict(self.metrics), self.metrics_at,
                    list(self.console) + ([self.partial] if self.partial else []))
