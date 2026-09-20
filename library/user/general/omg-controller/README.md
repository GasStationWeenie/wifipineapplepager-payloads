# O.MG Controller 1.6.4

Author: Gas Station Hot Dog

Empty slots are skipped for manual and automatic backups. Normal dialog
cancellation backs out of menus or cancels the current prompt without saving.
Cancelling the main menu exits. HUP, INT and TERM stop the controller and clean
up its helper; UI commands terminated by a signal also exit instead of reopening
a menu. The Pager firmware's stop behavior still needs hardware verification:
if it reports stopping as ordinary cancellation instead of a signal, the script
cannot distinguish that from a normal Back press.

Reboot displays reconnect instructions, sends the command once and exits.
It has no confirmation, echo/status preflight, acknowledgement wait or reconnect
check. A connection is opened only if needed to send the command. Wait for the O.MG
AP to return, reconnect the Pager, then relaunch the payload. No menus are opened
after reboot. This release uses the exit-and-relaunch flow, not automatic Wi-Fi
reconnection. Stopping this controller does not stop an already submitted O.MG
USB payload.

Controls an O.MG device at the fixed address `192.168.4.1` while the Pager is
connected to its Wi-Fi. Uses a persistent WebSocket connection and requires
Pager firmware 1.0.8+, Python 3.9+, and TEXT_PICKER for editing. Targets the
user's O.MG firmware v3.0.16.250816; hardware verification is still needed for
new changes.

## Backups and restores

The populated payload menu is **Execute, View, Edit, Backup Payload,
Restore Payload Backup, Clear Slot, Back**. Clear Slot requires confirmation.
Empty slots offer Write new, Import .txt, Restore Payload Backup and Back.

Manual backups, saves, clears and restores save nonempty prior payload source as
UTF-8 text in `$PAYLOAD_HOME/backups/`. Names use the slot number, up to ten
characters of the preview title and the Pager's local date/time:
`001-My payload-2026-09-19_14-30-25.txt`. The title omits a leading REM token and
its following spaces/tabs; filename-unsafe characters are replaced with underscores.
Blank titles use Empty. Same-second collisions add -2, -3, etc. Backups preserve
source whitespace and line endings, without flash padding or terminators.

Restore Payload Backup in a payload menu targets that slot. Under Extra, restore
first offers the original slot; No opens a destination picker with populated
slots followed by New Slot (empty). Restores require confirmation, back up a
nonempty destination first, check capacity and conflicts, and verify the written source.
An empty text backup restores an empty payload. Only filenames matching the
format above are accepted; the leading slot number identifies the original slot.

The Payloads list shows populated slots and empty gaps labeled Create New,
plus one empty allocated slot after the last populated slot. If all are empty,
only the first allocated slot is shown. No unallocated slots are invented.

## Installation / update

Requires Pager firmware **1.0.8+** and **Python 3.9+**. If Python is missing,
install it while the Pager has Internet access:

```sh
opkg update
opkg install -d mmc python3
LD_LIBRARY_PATH=/mmc/usr/lib:/mmc/lib python3 --version
```

Do not upgrade system packages. The WebSocket dependency is bundled; no pip or
Internet connection is needed when controlling O.MG.

Exit any running version, extract the ZIP and copy the **entire** `omg-controller`
folder (including `session.py`, `ducky.py` and `vendor`) to:

```
/root/payloads/user/general/omg-controller/
```

Preserve Unix LF endings, then run on the Pager:

```sh
chmod +x /root/payloads/user/general/omg-controller/payload.sh
```

Launch from **Payloads > User > General > O.MG Controller**. Category display can
vary. `PAYLOAD_HOME` locates assets even when the launcher runs from `/tmp`.
The MMC Python library-path fix from 1.0.1 is retained.

## Menu

- **Device status:** firmware, type, MAC, uptime, heap and diagnostic codes.
- **Payloads:** refreshes the directory and reads the first 256 bytes of
  each slot. Shows empty gaps as Create New and populated slots with the
  first nonblank line as a preview, omitting its leading `REM` and whitespace.
  This is a content preview, not an API-provided name or guarantee of executable
  content; whitespace-only slots can still appear.
  Choose a populated slot for its action menu; Create New opens creation,
  import and restore options for an unused slot.
- **Import .txt:** selecting a file saves it directly into the empty slot without
  opening the editor. Capacity, empty-slot and write verification checks remain.
  Backup restore behavior is unchanged.
- **View:** reads the full source to its terminator or allocated size. Shows
  ten display rows per page, with line numbers and wrapped long lines. Press A
  for Next/Previous/Back. Source is held in memory, not saved to Pager storage.
- **Execute:** reads and validates the whole source, then executes without confirmation.
  Transmits that validated snapshot without modifying the stored slot.
- **Payload status** and **Reboot**.
- **USB descriptors:** View current or Edit VID, PID, Manufacturer, Product and Serial.
- **Extra:** USB on/off, Jiggler on/off, Connection timing and Restore Payload Backup.

Directory refresh occurs each time a slot browser is opened. Basic controls never
scan slots. Exiting does not undo device settings; turn the jiggler off explicitly.

## Execution compatibility

Ordinary O.MG slots hold **source text**. The official frontend reads and compiles
that text before sending it through `CE`; this implementation does not assume a
universal run-by-slot command.

This release includes a **limited, strict US-layout compiler**, supporting:

- `REM`, `REM_BLOCK` / `END_REM`.
- `STRING`, `STRINGLN`, `STRING_BLOCK` / `END_STRING`, and
  `STRINGLN_BLOCK` / `END_STRINGLN`.
- `DELAY`, `DEFAULT_DELAY`, `DEFAULT_CHAR_DELAY` in milliseconds, at 10 ms resolution.
- `DUCKY_LANG US` (US is the default).
- `REPEAT count command` (O.MG inline syntax), up to 1000 repeats.
- Common named keys, F1-F12, modifier chords such as `CTRL ALT DELETE` and `GUI r`.
- `USB ON/OFF`, `JIGGLER ON/OFF`, `USB_RESET`, `CAPSLOCK_DISABLE`.

Functions, DEFINE substitution, non-US layouts, randomization, geofencing, mouse
commands and other unlisted extensions are **not implemented**. Unsupported syntax
rejects the entire script **before any execution data is sent**. Use the O.MG web
UI for those scripts. Binary-only slots cannot be viewed as original source or
executed through this compiler. This is not a full browser-compiler replacement.

Frames use 1008-character bytecode segments and CRC-16/AUG-CCITT over uppercase
hexadecimal text, matching the official frontend. Maximum: 255 segments. The
backend must report Idle before execution. A status query follows each segment
to surface errors. Failed writes are never automatically replayed. “Submitted”
does not confirm that the attached USB host processed the payload successfully.

## Speed

Earlier releases started Python, imported dependencies, connected, and disconnected
for **every action**, buffering all output until exit. Version 1.1.0 keeps one
Python helper and WebSocket for the menu session, displaying responses immediately.
A read-only echo checks a reused connection before each network action. Reconnection
can happen before an action; the action itself is never replayed after failure.

**Connection timing** reports three echo round trips. This measures network/device
latency after connection, not Python startup or UI rendering. No hardware-measured
speedup is claimed. Payload scanning still takes roughly one read per slot.
Full viewing reads 1024-byte chunks
only as far as the source terminator.

## Editing

Choose **Payloads > a populated slot > Edit**, or choose **Create New**. Select
a numbered line to Edit line, Insert before, or Delete line. Append line adds at
the end. The Pager text picker edits one line at a time. Empty lines, spaces and
tabs are preserved. Existing LF/CRLF endings are retained; inserted lines use
the source's newline style. Discard abandons the draft without changing flash.

Save asks for confirmation, checks slot capacity and whether the device's source
changed while editing, and backs up the original payload source to
`$PAYLOAD_HOME/backups/NNN-preview-YYYY-MM-DD_HH-MM-SS.txt`. It erases only the selected slot's
sectors, writes aligned chunks, and verifies the entire allocation by reading it
back. A disconnected/failed write is not replayed; the slot may be incomplete,
but its original text backup remains on the Pager. Keep that backup for recovery.
The editor and backups require writable storage in the installed payload folder.

Slots paired with **bootscript** cannot be saved here: use the O.MG web editor,
which also rebuilds the compiled boot payload. Saving arbitrary source does not
expand the controller's supported execution language subset. Editing reads the
whole slot allocation for backup/conflict checking, so it takes longer than View.
Longer scripts may be more comfortable to edit in the O.MG web UI.

## Troubleshooting and testing

Copy the whole directory if helper files are missing. If the shared-library error
persists, check that `libpython3.11.so.1.0` exists under `/mmc/usr/lib`; a search
path cannot replace a missing library.

The source reader follows the official v3 frontend's decimal sector map and tagged
flash-read layout. Incomplete reads and incompatible layouts fail rather than
being silently executed. If a slot read fails, retain its exact error and firmware
version. Authentication added by other firmware versions is not implemented.

Tests use a local WebSocket simulator and Pager UI stubs, covering connection reuse,
pagination, slot 200, erased slots, multiblock source, compiler vectors, unsupported
syntax, submission, disconnects, navigation/cancellation and staged `PAYLOAD_HOME`
launch. New features and speed still need verification on actual hardware.

## Sources and licensing

Bundled example: [OMG-TTS-Windows.txt by Kalani](https://github.com/hak5/omg-payloads/blob/master/payloads/library/prank/OMG-TTS-Windows.txt),
unchanged from Hak5's repository with its original author credit.

- [Hak5 payloads](https://documentation.hak5.org/wifi-pineapple-pager/payloads-1/introduction-to-payloads)
- [LIST_PICKER](https://documentation.hak5.org/wifi-pineapple-pager/list_picker)
- [PAYLOAD_HOME](https://documentation.hak5.org/wifi-pineapple-pager/payloads-1/advanced-payloads)
- [External packages](https://documentation.hak5.org/wifi-pineapple-pager/external-packages)
- [O.MG API](https://github.com/O-MG/O.MG-Firmware/wiki/WebSocket-API)
- [Official frontend](https://github.com/O-MG/O.MG-Firmware/blob/stable/c2server/index.html):
  `apiResponseCFList`, `payloadSlotLoad`, `payloadSlotSave`, `payloadRun`,
  `split_process`, `crc16augccitt`, `handleDelayCommands`.

Bundled: unmodified **websocket-client 1.9.0**, Apache-2.0, license included in its
metadata. This controller is not an official Hak5/O.MG integration.
