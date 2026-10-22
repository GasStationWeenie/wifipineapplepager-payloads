#!/bin/bash
# Title: ADSBee Airspace
# Description: Live aircraft list, radar map, interactive console and receiver metrics over client Wi-Fi
# Author: Gas Station Hot Dog
# Version: 1.0.4
# Category: Aviation

# Pager executes a temporary script. _PAYLOAD_HOME points to installed assets.
PAYLOAD_DIR="${_PAYLOAD_HOME:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
LOG_DIR="${ADSBEE_LOG_DIR:-/root/loot/adsbee}"
if ! mkdir -p "$LOG_DIR" || ! : >"$LOG_DIR/session.log"; then
    PROMPT "Cannot write /root/loot/adsbee. Check storage via SSH."
    exit 1
fi
exec 2>>"$LOG_DIR/session.log"
printf 'ADSBee 1.0.4\nPayload: %s\nLogs: %s\n' "$PAYLOAD_DIR" "$LOG_DIR" >>"$LOG_DIR/session.log"
export PATH="/mmc/usr/bin:$PATH"
export LD_LIBRARY_PATH="/mmc/usr/lib:$PAYLOAD_DIR/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$PAYLOAD_DIR/lib:${PYTHONPATH:-}"
APP_PID=""
UI_STOPPED=0

restore_ui() {
    if [ -n "$APP_PID" ]; then
        kill "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
        APP_PID=""
    fi
    if [ "$UI_STOPPED" = 1 ]; then
        /etc/init.d/pineapplepager start
        UI_STOPPED=0
    fi
}
trap restore_ui EXIT
trap 'exit 0' INT TERM HUP

for command in LIST_PICKER IP_PICKER TEXT_PICKER PAYLOAD_GET_CONFIG PAYLOAD_SET_CONFIG; do
    if ! command -v "$command" >/dev/null 2>&1; then
        LOG red "ADSBee requires Pager firmware 1.0.8+ with LIST_PICKER."
        exit 1
    fi
done

check_runtime() {
    {
        printf 'Payload: %s\n' "$PAYLOAD_DIR"
        if ! command -v python3; then
            echo "Python3 is not installed or is not on PATH."
            return 1
        fi
        python3 -c 'import ctypes, socket, json, hashlib, threading, math, argparse, ipaddress; import pagerctl'
    } >"$LOG_DIR/runtime-check.log" 2>&1
}

show_error() {
    printf 'ERROR: %s\n' "$*" >>"$LOG_DIR/session.log"
    LOG red "$*"
    # ERROR_DIALOG is non-blocking. PROMPT keeps the menu from covering errors.
    PROMPT "$*"
}

run_logged() {
    local -a results
    "$@" 2>&1 | tee -a "$LOG_DIR/install.log" | while IFS= read -r line || [ -n "$line" ]; do
        LOG "$line"
    done
    results=("${PIPESTATUS[@]}")
    [ "${results[0]}" = 0 ] && [ "${results[1]}" = 0 ]
}

install_runtime() {
    PROMPT "Install Python3 + ctypes to MMC. Internet is required."
    if ! : >"$LOG_DIR/install.log"; then
        show_error "Cannot create install.log in /root/loot/adsbee."
        return 1
    fi
    printf 'ADSBee runtime installation\nPayload: %s\n' "$PAYLOAD_DIR" >>"$LOG_DIR/install.log"
    LOG "Logs: /root/loot/adsbee/install.log"
    LOG green "Step 1/3: Updating package lists..."
    if ! run_logged opkg update; then
        show_error "Package update failed. See /root/loot/adsbee/install.log."
        return 1
    fi
    LOG green "Step 2/3: Installing Python3 + ctypes to MMC..."
    if ! run_logged opkg -d mmc install python3 python3-ctypes; then
        show_error "Package install failed. See /root/loot/adsbee/install.log."
        return 1
    fi
    LOG green "Step 3/3: Checking Python and graphics library..."
    if ! check_runtime; then
        cat "$LOG_DIR/runtime-check.log" >>"$LOG_DIR/install.log"
        while IFS= read -r line; do LOG red "$line"; done <"$LOG_DIR/runtime-check.log"
        show_error "Runtime check failed. See /root/loot/adsbee/runtime-check.log."
        return 1
    fi
    printf 'Runtime ready\n' >>"$LOG_DIR/install.log"
    LOG green "Runtime ready."
    PROMPT "Runtime ready. Continue to the ADSBee menu."
}

configure_ip() {
    local picked
    picked=$(IP_PICKER "ADSBee IPv4 address" "$HOST") || return 1
    [ -n "$picked" ] || return 1
    PAYLOAD_SET_CONFIG adsbee_airspace host "$picked" || { show_error "Could not save IP"; return 1; }
    HOST="$picked"
}

HOST=$(PAYLOAD_GET_CONFIG adsbee_airspace host 2>/dev/null) || HOST=""
PORT=$(PAYLOAD_GET_CONFIG adsbee_airspace port 2>/dev/null) || PORT=80
LAT=$(PAYLOAD_GET_CONFIG adsbee_airspace latitude 2>/dev/null) || LAT=""
LON=$(PAYLOAD_GET_CONFIG adsbee_airspace longitude 2>/dev/null) || LON=""
[ -n "$PORT" ] || PORT=80
[ -n "$HOST" ] || configure_ip || exit 0

while true; do
    CHOICE=$(LIST_PICKER "ADSBee $HOST" "Aircraft list" "Radar map" "Console" "Live metrics" "Change IP" "Map center" "HTTP port" "Install runtime" "Exit" "Aircraft list") || CHOICE="Exit"
    case "$CHOICE" in
        "Exit")
            EXIT_CHOICE=$(LIST_PICKER "Exit ADSBee payload?" "Keep running" "Exit payload" "Keep running") || continue
            [ "$EXIT_CHOICE" = "Exit payload" ] && exit 0
            continue ;;
        "Change IP") configure_ip || true; continue ;;
        "Install runtime")
            install_runtime || true
            continue ;;
        "Map center")
            CENTER_MODE=$(LIST_PICKER "Radar center" "Receiver automatic" "Saved coordinates" "Cancel" "Receiver automatic") || continue
            case "$CENTER_MODE" in
                "Receiver automatic")
                    PAYLOAD_DEL_CONFIG adsbee_airspace latitude
                    PAYLOAD_DEL_CONFIG adsbee_airspace longitude
                    LAT=""; LON="" ;;
                "Saved coordinates")
                    if ! check_runtime; then show_error "Runtime unavailable. Choose Install runtime. Details: /root/loot/adsbee/runtime-check.log"; continue; fi
                    NEW_LAT=$(TEXT_PICKER "Center latitude (-90..90)" "$LAT") || continue
                    NEW_LON=$(TEXT_PICKER "Center longitude (-180..180)" "$LON") || continue
                    if python3 "$PAYLOAD_DIR/settings.py" center "$NEW_LAT" "$NEW_LON"; then
                        PAYLOAD_SET_CONFIG adsbee_airspace latitude "$NEW_LAT" &&
                        PAYLOAD_SET_CONFIG adsbee_airspace longitude "$NEW_LON" && { LAT="$NEW_LAT"; LON="$NEW_LON"; }
                    else
                        show_error "Invalid decimal latitude/longitude"
                    fi ;;
            esac
            continue ;;
        "HTTP port")
            if ! check_runtime; then show_error "Runtime unavailable. Choose Install runtime. Details: /root/loot/adsbee/runtime-check.log"; continue; fi
            NEW_PORT=$(TEXT_PICKER "ADSBee HTTP port" "$PORT") || continue
            if python3 "$PAYLOAD_DIR/settings.py" port "$NEW_PORT"; then
                PAYLOAD_SET_CONFIG adsbee_airspace port "$NEW_PORT" && PORT="$NEW_PORT"
            else show_error "Port must be 1..65535"; fi
            continue ;;
        "Aircraft list") VIEW=LIST ;;
        "Radar map") VIEW=MAP ;;
        "Console") VIEW=CONSOLE ;;
        "Live metrics") VIEW=METRICS ;;
        *) continue ;;
    esac
    if ! check_runtime; then
        show_error "Runtime unavailable. Choose Install runtime. Details: /root/loot/adsbee/runtime-check.log"
        continue
    fi
    if ! python3 "$PAYLOAD_DIR/settings.py" host "$HOST" "$PORT"; then
        show_error "Invalid saved IP or port; change it in this menu."
        continue
    fi
    ARGS=(--host "$HOST" --port "$PORT" --view "$VIEW")
    if [ -n "$LAT" ] && [ -n "$LON" ]; then ARGS+=(--center "$LAT" "$LON"); fi
    LOG "ADSBee: B asks before leaving. L/R switches views."
    UI_STOPPED=1
    /etc/init.d/pineapplepager stop || { restore_ui; exit 1; }
    python3 -u "$PAYLOAD_DIR/adsbee.py" "${ARGS[@]}" >"$LOG_DIR/runtime.log" 2>&1 &
    APP_PID=$!
    wait "$APP_PID"
    RESULT=$?
    APP_PID=""
    restore_ui
    if [ "$RESULT" != 0 ]; then
        show_error "Viewer stopped. See /root/loot/adsbee/runtime.log."
    fi
done
