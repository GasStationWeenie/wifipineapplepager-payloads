#!/bin/bash
# Title: GPS Phone HotSpot Client AP Mode
# Author: GSHD (+ cncartist)
# Description: Turn your phone into your GPS for the Pager with minimal effort!  Allows stop/start of UDP Port 9999 NMEA GPS data collection for the Pager.  Can use Android app gpsdRelay, iPhone NMEA Send Location App, C5 Wardriver, or similar GPS relaying apps/devices to relay NMEA information to the gpsd server UDP Port 9999 while connected to a phone hotspot. It can take some time until data starts being received, and that relies on the phone/sending devices GPS signal.
# Category: general
# 
# ============================================
# Acknowledgements: 
# ============================================
# cncartist - https://github.com/cncartistsec/ - Original Script
# repins762 - https://github.com/repins762 - (idea)
# mobile2gps (https://github.com/ryanpohlner/mobile2gps/tree/main) - Author: Ryan Pohlner (@Spectracide on Discord) - (insight)
# gpsdRelay (https://f-droid.org/packages/io.github.project_kaat.gpsdrelay/) - Author: project-kaat (Android Relay)
# NMEA Send Location App (https://apps.apple.com/us/app/nmea-send-location/id6749798097) - Author: Alexey Matveev (iPhone Relay)
#
# ============================================
# Notes:
# ============================================
# ORIG FW 1.0.9 = option device '/dev/serial/by-path/1.1_1-1.1:1.0'
# Check output of active GPS data with count of 10 new messages: "gpspipe -r -n 10"
# -- -- Output will be flowing when GPS is coming through
# 

backupFile="savedGPSdevice.txt"
RULE_NAME="gps_access_rule"

LOG blue "========================================"
LOG      "======= GPS NMEA Phone Hotspot AP ======"
LOG      "======== EXTERNAL GPS ENABLER =========="
LOG      "==== UDP Port 9999 (NMEA) GGA & RMC ===="
LOG blue "========================================"
LOG " "

resp=$(CONFIRMATION_DIALOG "Do you want to ENABLE GPS NMEA Relay on UDP port 9999?
	
	This will change the device path for GPS to listen to UDP port 9999.")
if [[ "$resp" == "$DUCKYSCRIPT_USER_CONFIRMED" ]] ; then
	LOG "Stopping GPS instances..."
	killall gpsd 2>/dev/null
	sleep 1
	LOG "Changing Device Path..."
	# check if file is not empty this time around
	if [[ -s "$backupFile" ]]; then
		# check if file exists, means it may have been running/restarting relay
		LOG "Saving Previous Settings..."
		orig_gpsdevicepath=$(cat "$backupFile")
	else
		orig_gpsdevicepath=$(uci get gpsd.core.device)
	fi
	# LOG "orig_gpsdevicepath: $orig_gpsdevicepath"
	printf "%s" "${orig_gpsdevicepath}" > "$backupFile"
	uci set gpsd.core.device='udp://0.0.0.0:9999'
	uci commit 2>/dev/null
	sleep 1
	LOG "Applying Settings..."
	/etc/init.d/gpsd reload 2>/dev/null
	/etc/init.d/gpsd restart 2>/dev/null
	sleep 1
	LOG green "GPS Enabled!"
	sleep 1
	LOG "Opening firewall port for Client AP..."
	
	uci set firewall.$RULE_NAME=rule
    uci set firewall.$RULE_NAME.name='Allow-Dev-Access'
    uci set firewall.$RULE_NAME.src='wan'
    uci set firewall.$RULE_NAME.dest_port='9999'
    uci set firewall.$RULE_NAME.proto='tcp'
    uci set firewall.$RULE_NAME.target='ACCEPT'
    uci set firewall.$RULE_NAME.enabled='1'

	uci reorder firewall.$RULE_NAME=0
	uci commit firewall
	fw4 restart
	
	sleep 1
	CLIENT_IP=$(ifconfig wlan0cli 2>/dev/null | grep 'inet addr' | cut -d: -f2 | awk '{print $1}')
	sleep 1

	LOG " "
	LOG "1. Connect to Phone Hotspot from Pager"
	LOG "2. Open gpsdRelay on Phone"
	LOG "3. Add Relay to ${CLIENT_IP}:9999 (UDP)"
	LOG "-- Options: 'NMEA relaying' ONLY to GGA & RMC"
	LOG "5. Start Phone Relay to Pager and Patience!"
	LOG " "
else 
	LOG "Skipped Enabling GPS..."
	LOG " "	
	resp=$(CONFIRMATION_DIALOG "Do you want to STOP/DISABLE GPS NMEA Relay on UDP port 9999?
	
	This will return the device path for GPS to the previous settings.")
	if [[ "$resp" == "$DUCKYSCRIPT_USER_CONFIRMED" ]] ; then
		LOG "Stopping GPS instances..."
		killall gpsd 2>/dev/null
		sleep 1
		# check if file is not empty this time around
		if [[ -s "$backupFile" ]]; then
			LOG "Returning Device to Previous Setting..."
			saved_gpsdevicepath=$(cat "$backupFile")
			# LOG "saved_gpsdevicepath: $saved_gpsdevicepath"
			uci set gpsd.core.device="$saved_gpsdevicepath"
			uci commit 2>/dev/null
		fi
		sleep 1
		LOG "Applying Settings..."
		/etc/init.d/gpsd reload 2>/dev/null
		/etc/init.d/gpsd restart 2>/dev/null
		sleep 1
		# remove old file
		rm "$backupFile" 2>/dev/null
		LOG "Removing firewall rule for 9999..."
		# remove fw rule
		uci delete firewall.$RULE_NAME 2>/dev/null
        uci commit firewall
        fw4 restart
		
		LOG green "Complete!"
		LOG " "
	else 
		LOG "Skipped Stopping GPS and removing firewall rule..."
		LOG " "
	fi
fi

LOG "Finished, exiting..."
LOG " "

exit 0
