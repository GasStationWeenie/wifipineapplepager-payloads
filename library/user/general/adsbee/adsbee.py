#!/usr/bin/env python3
"""ADSBee's four live views on a 480x222 Pineapple Pager display."""
import argparse
import math
from pathlib import Path
import signal
import sys
import time

from model import State, clean, coordinates, flatten, number, relative
from wire import Feed

TABS = ("LIST", "MAP", "CONSOLE", "METRICS")
RANGES = (5, 10, 25, 50, 100, 200)
KEYS = [list(row) for row in ["1234567890", "QWERTYUIOP", "ASDFGHJKL?", "ZXCVBNM=+-", ".,:;/_()[]", "'\"\\@!#$%&*"]]
KEYS.append(list("`<>^|{}~"))
KEYS.append(["SPACE", "DEL", "CASE", "SEND", "CANCEL"])


def value(plane, key, suffix=""):
    v = plane.get(key)
    if v is None:
        return "--"
    n = number(v)
    return (f"{n:.0f}" if n is not None else clean(v, 14)) + suffix


def dispatch_buttons(pager, app, held):
    """Consume individual edges so a tap between frames cannot disappear."""
    for _ in range(128):
        event = pager.get_input_event()
        if event is None:
            break
        button, kind, _ = event
        if kind == pager.EVENT_RELEASE:
            held &= ~button
        elif kind == pager.EVENT_PRESS and not held & button:
            held |= button
            app.input(button)
            if not app.running:
                break
    return held


class App:
    def __init__(self, pager, state, feeds, center=None, initial="LIST"):
        self.p, self.state, self.feeds, self.center = pager, state, feeds, center
        self.tab = TABS.index(initial)
        self.selected = None
        self.range_index = 3
        self.offset = 0
        self.detail = False
        self.editing = False
        self.confirm_exit = False
        self.command = ""
        self.key_row, self.key_col, self.lower = 0, 0, False
        self.running = True
        self.bg = pager.rgb(6, 15, 25)
        self.panel = pager.rgb(15, 32, 46)
        self.ink = pager.rgb(224, 238, 242)
        self.muted = pager.rgb(115, 144, 158)
        self.accent = pager.rgb(55, 226, 185)
        self.yellow = pager.rgb(255, 202, 90)
        self.grid = pager.rgb(33, 65, 78)
        self.planes = []

    def text(self, x, y, text, color=None, size=1, width=480):
        # pagerctl bitmap font advances 6 pixels at scale 1.
        limit = max(0, (width - x) // (6 * size))
        self.p.draw_text(x, y, clean(text, limit), self.ink if color is None else color, size)

    def ordered(self, planes):
        return sorted(planes, key=lambda p: (relative(p, self.center) or (float("inf"), 0))[0])

    def select(self, step):
        ids = [p["hex"] for p in self.planes]
        if ids:
            at = ids.index(self.selected) if self.selected in ids else 0
            self.selected = ids[(at + step) % len(ids)]

    def input(self, pressed):
        p = self.p
        if self.confirm_exit:
            if pressed & p.BTN_B:
                self.confirm_exit = False
            elif pressed & p.BTN_A:
                self.running = False
            return
        if self.editing:
            self.keyboard_input(pressed)
            return
        if pressed & p.BTN_B:
            if self.tab == 0 and self.detail:
                self.detail = False
            else:
                self.confirm_exit = True
        elif pressed & (p.BTN_LEFT | p.BTN_RIGHT):
            self.tab = (self.tab + (1 if pressed & p.BTN_RIGHT else -1)) % 4
            self.offset, self.detail = 0, False
        elif pressed & (p.BTN_UP | p.BTN_DOWN):
            step = -1 if pressed & p.BTN_UP else 1
            if self.tab == 0:
                self.select(step)
            elif self.tab == 1:
                self.range_index = max(0, min(len(RANGES) - 1, self.range_index + step))
            else:
                self.offset = max(0, self.offset - step if self.tab == 2 else self.offset + step)
        elif pressed & p.BTN_A:
            if self.tab == 0:
                self.detail = not self.detail
            elif self.tab == 1:
                self.select(1)
            elif self.tab == 2:
                self.editing = True
                self.key_row, self.key_col = 0, 0
            else:
                self.offset = 0

    def keyboard_input(self, pressed):
        p = self.p
        if pressed & p.BTN_B:
            self.editing = False
        elif pressed & p.BTN_UP:
            self.key_row = (self.key_row - 1) % len(KEYS)
        elif pressed & p.BTN_DOWN:
            self.key_row = (self.key_row + 1) % len(KEYS)
        elif pressed & p.BTN_LEFT:
            self.key_col -= 1
        elif pressed & p.BTN_RIGHT:
            self.key_col += 1
        elif pressed & p.BTN_A:
            key = KEYS[self.key_row][self.key_col % len(KEYS[self.key_row])]
            if key == "CANCEL":
                self.editing = False
            elif key == "CASE":
                self.lower = not self.lower
            elif key == "DEL":
                self.command = self.command[:-1]
            elif key == "SEND":
                if self.command.strip():
                    sent = self.feeds["/console"].command(self.command)
                    self.state.text("\n> " + self.command + "\n" if sent else "\n[Offline: command NOT sent]\n")
                    if sent:
                        self.command = ""
                        self.editing = False
                        self.offset = 0
            elif len(self.command) < 240:
                self.command += " " if key == "SPACE" else key.lower() if self.lower else key
        self.key_col %= len(KEYS[self.key_row])

    def frame(self):
        planes, metrics, metrics_at, console = self.state.snapshot()
        self.planes = self.ordered(planes)
        if self.selected not in [p["hex"] for p in self.planes]:
            self.selected = self.planes[0]["hex"] if self.planes else None
        p = self.p
        p.clear(self.bg)
        for i, title in enumerate(TABS):
            p.fill_rect(i * 120, 0, 118, 21, self.accent if i == self.tab else self.panel)
            self.text(i * 120 + 8, 7, title, self.bg if i == self.tab else self.muted)
        path = ("/aircraft", "/aircraft", "/console", "/metrics")[self.tab]
        feed = self.feeds[path]
        age = "" if feed.last_rx is None else f" | RX {time.monotonic() - feed.last_rx:.0f}s ago"
        self.text(7, 27, feed.status + age, self.accent if feed.status == "Connected" else self.yellow)
        if self.editing:
            self.keyboard()
        elif self.tab == 0:
            self.list_view()
        elif self.tab == 1:
            self.map_view()
        elif self.tab == 2:
            self.console_view(console)
        else:
            self.metrics_view(metrics, metrics_at)
        p.fill_rect(0, 202, 480, 20, self.panel)
        help_text = ("UP/DN select | A details", "UP/DN zoom | A next plane",
                     "UP/DN scroll | A type command", "UP/DN scroll | A top")[self.tab]
        if self.editing:
            help_text = "DPAD move | A key | B close keyboard"
        back_action = "B list" if self.tab == 0 and self.detail else "B leave"
        self.text(5, 209, help_text + ("" if self.editing else " | L/R view | " + back_action), self.muted)
        if self.confirm_exit:
            self.exit_dialog()
        p.flip()

    def exit_dialog(self):
        self.p.fill_rect(35, 53, 410, 138, self.panel)
        self.text(55, 70, "Leave live viewer?", self.yellow, 2)
        self.text(55, 100, "Returning to the menu reloads the Pager UI.")
        self.text(55, 124, "A / GREEN: Leave viewer", self.yellow)
        self.text(55, 147, "B / RED: Keep watching", self.accent)
        self.text(55, 170, "Live data stays connected while you decide.", self.muted)

    def list_view(self):
        if not self.planes:
            self.text(12, 73, "Waiting for aircraft...", self.accent, 2)
            self.text(12, 105, "Verify Wi-Fi, IP and ADSBee Live Map support.", self.muted)
            return
        selected = next(p for p in self.planes if p["hex"] == self.selected)
        if self.detail:
            self.text(10, 45, selected.get("flight", "").strip() or selected["hex"], self.accent, 2)
            rel = relative(selected, self.center)
            pos = coordinates(selected.get("lat"), selected.get("lon"))
            rows = [f"ID {selected['hex']}  Squawk {selected.get('squawk', '--')}",
                    f"Altitude {value(selected, 'alt_baro', ' ft')}  Speed {value(selected, 'gs', ' kt')}",
                    f"Track {value(selected, 'track', ' deg')}  V/S {value(selected, 'baro_rate', ' fpm')}",
                    f"Range {rel[0]:.1f} nm  Bearing {rel[1]:.0f} deg" if rel else "Range unknown: configure center in menu",
                    f"Lat {pos[0]:.5f}  Lon {pos[1]:.5f}" if pos else "No valid position",
                    f"Source {selected.get('type', '--')} / {selected.get('link', '--')}",
                    f"RSSI {value(selected, 'rssi', ' dBm')}  Position age {time.monotonic()-selected['position_at']:.0f}s"]
            for i, row in enumerate(rows):
                self.text(10, 73 + i * 17, row)
            return
        for x, label in ((9,"CALL"),(104,"ICAO"),(207,"ALT ft"),(309,"KT"),(381,"NM"),(438,str(len(self.planes)))):
            self.text(x, 44, label, self.muted)
        at = next(i for i, p in enumerate(self.planes) if p["hex"] == self.selected)
        start = max(0, at - 5)
        for i, plane in enumerate(self.planes[start:start + 6]):
            y = 61 + i * 23
            active = plane["hex"] == self.selected
            if active:
                self.p.fill_rect(5, y - 4, 470, 21, self.panel)
            label = clean(plane.get("flight", "").strip() or plane["hex"], 10)
            rel = relative(plane, self.center)
            stale = time.monotonic() - plane["received"] > 15
            self.text(9, y, ("> " if active else "  ") + label, self.accent if active else self.muted if stale else self.ink)
            self.text(104, y, plane["hex"], self.muted)
            self.text(207, y, value(plane, "alt_baro"))
            self.text(309, y, value(plane, "gs"))
            self.text(381, y, f"{rel[0]:.1f}" if rel else "--")

    def map_view(self):
        p = self.p
        cx, cy, radius = 121, 119, 77
        scale = RANGES[self.range_index]
        for r in (radius // 2, radius):
            p.circle(cx, cy, r, self.grid)
        p.line(cx - radius, cy, cx + radius, cy, self.grid)
        p.line(cx, cy - radius, cx, cy + radius, self.grid)
        p.fill_circle(cx, cy, 3, self.ink)
        self.text(cx - 3, 40, "N", self.accent)
        self.text(8, 187, f"{scale} nm / ring {scale/2:g}", self.muted)
        self.text(235, 44, "NORTH UP", self.accent)
        self.text(235, 58, "Saved center" if self.center else "Receiver center", self.muted)
        visible, located = 0, 0
        now = time.monotonic()
        selected = None
        for plane in self.planes:
            rel = relative(plane, self.center)
            if not rel or now - plane["position_at"] > 60:
                continue
            located += 1
            distance, bearing = rel
            if plane["hex"] == self.selected:
                selected = plane
            if distance > scale:
                continue
            visible += 1
            angle = math.radians(bearing)
            x = round(cx + math.sin(angle) * distance / scale * radius)
            y = round(cy - math.cos(angle) * distance / scale * radius)
            active = plane["hex"] == self.selected
            color = self.yellow if active else self.muted if now - plane["position_at"] > 15 or now-plane["received"] > 15 else self.accent
            track = number(plane.get("track"))
            if track is None:
                p.fill_circle(x, y, 2, color)
            else:
                t = math.radians(track)
                points = [(round(x + math.sin(t+a)*r), round(y-math.cos(t+a)*r)) for a, r in ((0, 6), (2.5, 4), (-2.5, 4))]
                for a, b in zip(points, points[1:] + points[:1]):
                    p.line(*a, *b, color)
            if active:
                p.circle(x, y, 8, self.yellow)
        self.text(235, 78, f"{visible} in view / {located} positioned")
        if not located:
            self.text(235, 105, "Waiting for positions", self.yellow)
            self.text(235, 122, "Set center in menu if", self.muted)
            self.text(235, 136, "no receiver range data.", self.muted)
        elif selected:
            rel = relative(selected, self.center)
            self.text(235, 103, selected.get("flight", "").strip() or selected["hex"], self.yellow, 2)
            self.text(235, 126, f"{rel[0]:.1f} nm  {rel[1]:.0f} deg")
            self.text(235, 143, value(selected, "alt_baro", " ft") + " / " + value(selected, "gs", " kt"))
            self.text(235, 160, "Pos age " + f"{now-selected['position_at']:.0f}s", self.muted)
            if rel[0] > scale:
                self.text(235, 177, "Selected plane off scale", self.yellow)
        self.text(235, 190, "Dim: >15s  Hide: >60s", self.muted)

    def console_view(self, rows):
        self.offset = min(self.offset, max(0, len(rows) - 1))
        end = max(0, len(rows) - self.offset)
        for i, row in enumerate(rows[max(0, end - 11):end]):
            self.text(5, 43 + i * 14, row)
        if not rows:
            self.text(8, 55, "A opens keyboard. Select SEND to execute.", self.accent)
            self.text(8, 75, "Console commands may change receiver settings.", self.muted)

    def metrics_view(self, metrics, at):
        if at is None:
            self.text(10, 65, "Waiting for live metrics...", self.accent, 2)
            return
        rows = flatten(metrics)
        self.offset = min(self.offset, max(0, len(rows) - 9))
        self.text(7, 43, f"Live metrics | {len(rows)} fields | scroll {self.offset+1}", self.muted)
        for i, (key, val) in enumerate(rows[self.offset:self.offset+9]):
            # Long source keys wrap into compact suffixes; full values remain scrollable as fields.
            label = key if len(key) <= 52 else ".." + key[-50:]
            self.text(7, 61 + i * 15, label, self.muted, width=330)
            self.text(337, 61 + i * 15, val, self.accent)

    def keyboard(self):
        self.text(7, 43, "> " + self.command[-73:], self.yellow)
        for row, keys in enumerate(KEYS):
            cell = 480 // len(keys)
            for col, key in enumerate(keys):
                x, y = col * cell, 61 + row * 17
                active = row == self.key_row and col == self.key_col
                self.p.fill_rect(x+1, y, cell-2, 15, self.accent if active else self.panel)
                label = key.lower() if len(key) == 1 and self.lower else key
                self.text(x+5, y+5, label, self.bg if active else self.ink)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--view", choices=TABS, default="LIST")
    parser.add_argument("--center", nargs=2, type=float)
    args = parser.parse_args()
    if args.center and coordinates(*args.center) is None:
        parser.error("Center must be latitude -90..90 and longitude -180..180")
    sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
    from pagerctl import Pager
    state = State()
    feeds = {path: Feed(args.host, path, callback, args.port) for path, callback in
             (("/aircraft", state.aircraft), ("/metrics", state.metric), ("/console", state.text))}
    p = Pager()
    if p.init() != 0:
        raise RuntimeError("Could not initialize Pager display")
    app = App(p, state, feeds, args.center, args.view)
    signal.signal(signal.SIGTERM, lambda *_: setattr(app, "running", False))
    signal.signal(signal.SIGINT, lambda *_: setattr(app, "running", False))
    try:
        p.set_rotation(270)
        for feed in feeds.values():
            feed.start()
        # Ignore the launch button until it is released.
        time.sleep(0.25)
        while p.get_input_event() is not None:
            pass
        held = p.peek_buttons()
        next_frame = 0
        while app.running:
            held = dispatch_buttons(p, app, held)
            now = time.monotonic()
            if app.running and now >= next_frame:
                app.frame()
                next_frame = time.monotonic() + 0.1
            time.sleep(0.01)
    finally:
        for feed in feeds.values():
            feed.stop()
        for feed in feeds.values():
            if feed.ident:
                feed.join(timeout=0.5)
        p.cleanup()


if __name__ == "__main__":
    main()
