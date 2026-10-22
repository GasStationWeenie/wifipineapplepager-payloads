# ADSBee Airspace for WiFi Pineapple Pager

**Author:** Gas Station Hot Dog  
**Version:** 1.0.4

A Pager user payload for an ADSBee 1090-family receiver reachable over client Wi-Fi. It connects directly to the receiver's existing WebSocket server, without a feeder computer, cloud API, map tiles, or an internet connection during use.

## Views

* **Aircraft list:** callsign/ICAO, barometric altitude in feet, ground speed in knots and distance in nautical miles. Select an aircraft for position, source, track, vertical speed, squawk and signal details. Unknown fields display `--`.
* **Radar map:** north-up, range rings, aircraft direction markers, selected-aircraft details, and 5/10/25/50/100/200 nm range. Aircraft without usable positions or receiver-relative coordinates remain in the list. This is a surrounding-aircraft display with no geographic basemap.
* **Console:** live receiver output with a 500-line scrollback and a D-pad keyboard for commands. Select **SEND** to submit. CASE switches upper/lower case; SPACE and DEL edit the command. All printable ASCII characters are available. Commands are sent only when requested; disconnected or failed sends are never automatically replayed. The input stays available after a failed send. The line viewer strips ANSI CSI color/control sequences; it is not a full terminal emulator.
* **Live metrics:** scroll the fields supplied by `/metrics`, including aircraft dictionary counters/rates, device status, CPU, memory and feed information when available in your firmware. It displays the receiver's actual fields rather than assuming a fixed firmware schema. The last-received age appears at the top.

IP, HTTP port and an optional map center are saved using Pager's persistent payload configuration. Every launch opens a menu with the remembered IP and **Change IP** available. The default HTTP port is 80.

The payload reads individual button press/release events at a 10 ms interval independently of the 10 Hz display refresh, so quick taps between frames are retained. Held buttons trigger once until released. It asks for confirmation before leaving the live viewer or exiting the payload menu. **B from aircraft details returns directly to the list**, preserving the selected aircraft. The viewer confirmation runs inside the existing screen: **A / green** leaves, **B / red** cancels, and live feeds stay connected while deciding. Closing aircraft details or the console keyboard does not prompt.

## Install

1. Copy the **entire adsbee folder** to `/root/payloads/user/general/` on your Pager
2. Connect the Pager in **client Wi-Fi mode** to the same network as your ADSBee, or to the ADSBee's own access point. Use Pager's normal Wi-Fi settings. Both devices must be reachable across the network; client isolation can prevent this. Enter the ADSBee's IP on that network, not the Pager's IP.
3. Open **Payloads → Aviation → ADSBee Airspace**. Pager firmware **1.0.8 or newer** is required for `LIST_PICKER`.
4. Enter the receiver's IPv4 address. If Python is unavailable, choose **Install runtime**. This explicitly installs `python3` and `python3-ctypes` to MMC using `opkg`; this step needs internet access and free space. It shows three stages (package-list update, package install, runtime check), streams package-manager output to the screen, and waits for acknowledgement on success or failure. An isolated ADSBee access point might not provide internet, so install before joining it. The payload does not replace existing system packages.
5. Select **Aircraft list**, **Radar map**, **Console**, or **Live metrics**.

The bundled graphics library is a community MIPS little-endian build of pagerctl. The runtime check tests that Python can load it before taking over the screen. Source is included under `vendor/pagerctl`. No pip packages are needed on the Pager.

## Controls

| View | D-pad up/down | A (green) | Left/right | B (red) |
| --- | --- | --- | --- | --- |
| Aircraft list | Select aircraft | Toggle details | Switch view | Ask to leave viewer |
| Aircraft details | Select aircraft | Return to list | Switch view | Return to list |
| Radar map | Zoom in/out | Select next aircraft | Switch view | Ask to leave viewer |
| Console | Scroll older/newer output | Open command keyboard | Switch view | Ask to leave viewer |
| Metrics | Scroll fields | Return to top | Switch view | Ask to leave viewer |
| Keyboard | Move between rows | Select key; SEND executes | Move between keys | Close keyboard |

Console commands can change or reboot your receiver. Nothing is sent automatically on launch. Start with `AT` for a basic console check. A send failure cannot prove whether the receiver executed a partially transmitted command; check output before manually trying again.

## Centering the radar

**Receiver automatic** uses ADSBee's `r_dst` (nm) and `r_dir` (degrees) fields when available. These refer to the receiver's configured/derived position, not the Pager's location. Newer firmware may provide these; older builds may only provide aircraft latitude and longitude.

If the map has no positioned targets, choose **Map center → Saved coordinates** and enter the decimal latitude and longitude of your receiver or another location of interest. For example, a negative longitude is west. The payload computes great-circle distances and bearings from aircraft coordinates, including across the date line. A saved center overrides receiver-relative fields. Choose **Receiver automatic** to clear it. There is no guessed center based on the aircraft cluster.

The map does not follow a moving Pager. Update the saved center when moving, or use a receiver with correctly updated receiver-relative coordinates. Position reports older than 15 seconds are dimmed and those older than 60 seconds are hidden from the map. Tracks not reported by the stream for 60 seconds are removed. Older firmware without `seen_pos` cannot communicate the original position age; local receipt time is used instead. Aircraft aren't extrapolated into predicted positions.

## Network behavior and troubleshooting

The payload opens three connections on the selected HTTP port: `/aircraft`, `/metrics`, and `/console`. This mirrors ADSBee's web interface. It supports individual aircraft objects and batched arrays; a batch is not treated as a complete snapshot. Each endpoint reconnects independently with a 1–15 second backoff. The display refreshes at 10 Hz; source update speed depends on ADSBee firmware and traffic. It shows connection failures and receive age. A connected aircraft stream can be quiet when there is no traffic.

* **Cannot connect:** check client Wi-Fi, address, HTTP port, routing, and firewall/client isolation. Try opening the receiver's web interface from another device on that network.
* **Upgrade rejected / no aircraft endpoint:** use firmware with the ADSBee Live Map `/aircraft` interface. A receiver that only offers UDP/raw Beast output is not supported by this payload. ADSBee 1421's UART-only interface is not supported.
* **Busy receiver:** close extra browser Live Map sessions if the receiver reaches its WebSocket client/socket limit.
* **Map empty but list populated:** set a center, increase range, and check whether the aircraft have valid positions. No callsign or position is invented for incomplete traffic.
* **Dependency/startup failure:** inspect `/root/loot/adsbee/install.log`, `/root/loot/adsbee/runtime-check.log`, and `/root/loot/adsbee/runtime.log` via SSH/SFTP. The runtime check preserves Python import errors, including graphics-library loading failures. Dependency installation is offered explicitly, never during a live view.
* **After a firmware update:** packages or native compatibility may change; the payload checks runtime imports on every launch.

The payload creates `/root/loot/adsbee` on launch. `session.log` records the installed payload path and errors; `install.log` records the most recent installation attempt; `runtime-check.log` records the latest dependency check; `runtime.log` captures viewer output and Python tracebacks. Each file is reset when its corresponding activity starts. Logs stay out of Pager's temporary payload directory.

The native viewer temporarily stops the Pager UI service, following pagerctl's integration pattern, and restores it when leaving the viewer or after a normal error/signal. If a hard interruption leaves the UI stopped, run `/etc/init.d/pineapplepager start` over SSH.

This display is for hobby observation. Reception and position data can be incomplete or stale; do not use it for navigation or collision avoidance.

## Preview Images
<img width="1000" height="790" alt="preview" src="https://github.com/user-attachments/assets/2d385850-e94b-4b75-bf30-2f7f6b555179" />


## Development and validation

```sh
python -m unittest discover -s tests -v
python tools/check_shell.py
python tools/preview.py
python tools/package.py
```

Preview rendering requires Pillow on the development computer only. `dist/preview.png` uses synthetic aircraft/metrics with the same renderer geometry and bitmap font as the payload. The preview is not a hardware screenshot.

The automated suite covers JSON record formats, independent batches, field invalidation, aging, projection/date-line handling, settings validation, console parsing, WebSocket masking, partial reads/timeouts, fragmentation and control frames, size limits, offline command handling, a real local mock WebSocket handshake/console exchange, and rendering/input smoke checks. The shell harness checks Bash syntax, saved-IP reuse and initial persistence, plus five mocked runtime/installation scenarios. It runs a temporary copy of the launcher with `_PAYLOAD_HOME` pointing to the installed assets, checks that package output reaches both the log file and Pager LOG, and checks that acknowledgement happens before returning to the menu. Physical Pager display/buttons, client Wi-Fi and a real ADSBee have **not been tested** in this workspace.

To rebuild `libpagerctl.so`, install Docker and run `python tools/build_pagerctl.py` from the project root, then repackage. The script uses pagerctl's documented OpenWrt MIPS SDK image. This rebuild was not run here because Docker is unavailable. The included binary is the pinned upstream artifact, with its SHA-256 recorded in `THIRD_PARTY.md`.

## Sources

Protocol implementation was checked against [PantsForBirds/adsbee](https://github.com/PantsForBirds/adsbee) commit `dac3f9c0629dcfc8c0aec145ffaf9ff18d6b2311`, specifically [server endpoints and batching](https://github.com/PantsForBirds/adsbee/blob/dac3f9c0629dcfc8c0aec145ffaf9ff18d6b2311/firmware/adsbee_1090/esp/main/server/adsbee_server.cpp), [web console/metrics client](https://github.com/PantsForBirds/adsbee/blob/dac3f9c0629dcfc8c0aec145ffaf9ff18d6b2311/firmware/adsbee_1090/esp/main/server/web/adsbee.js), and [aircraft JSON fields](https://github.com/PantsForBirds/adsbee/blob/dac3f9c0629dcfc8c0aec145ffaf9ff18d6b2311/firmware/common/comms/aircraftjson/aircraftjson_utils.hh). No ADSBee firmware code is copied into the payload.

Pager behavior was checked through the configured pineapplePagerDocs MCP: [IP picker](https://documentation.hak5.org/wifi-pineapple-pager/ip_picker), [persistent configuration](https://documentation.hak5.org/wifi-pineapple-pager/config), [list picker](https://documentation.hak5.org/wifi-pineapple-pager/list_picker), [installation](https://documentation.hak5.org/wifi-pineapple-pager/payloads-1/installing-payloads), and [advanced payloads/packages](https://documentation.hak5.org/wifi-pineapple-pager/payloads-1/advanced-payloads). Graphics use [community pagerctl](https://github.com/pineapple-pager-projects/pineapple_pager_pagerctl); this is not an official Hak5 graphics API.
