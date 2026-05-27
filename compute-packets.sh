#!/bin/bash
# compute-packets.sh — regenerate pre-computed BLE advertising packets
# Run whenever the UUID in .env changes

cd "$(dirname "$0")"
addr=$(printf "0x%08x\n" $((0x$(jq -r '.lu' .env | cut -d- -f2-3 | tr -d -) + 1)))

echo "# Pre-computed BLE advertising packets for UUID: $(jq -r '.lu' .env)"
echo "# Generated: $(date)"
echo "BIND_DATA=\"$(./lampctrl -a $addr -b 1)\""
echo "ON_DATA=\"$(./lampctrl -a $addr -o 1)\""
echo "OFF_DATA=\"$(./lampctrl -a $addr -o 0)\""
