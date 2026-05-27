#!/bin/bash
# send-relay.sh — send lamp commands via Pi BLE proxy
# Usage: ./send-relay.sh <pi-host> on|off|bind|dim [orange] [white]
# Example: ./send-relay.sh pi3b.local on

PI="${1:-pi3b.local}"
CMD="${2:-on}"
PORT="${3:-8765}"
shift 2 2>/dev/null || true

cd "$(dirname "$0")"

# Pre-computed advertising data for bind/on/off (from UUID in .env)
# If UUID changes, run: ./compute-packets.sh to regenerate
BIND_DATA="-u 08f0 -u 8030 -u 75b8 -u 27e1 -u fe02 -u 7f55 -u 4465 -u 9fa4 -u f667 -u 57b6 -u 8bd0 -u 2b53 -u 2b9f"
ON_DATA="-u 08f0 -u 8030 -u 75b8 -u 27e1 -u fe02 -u 7f55 -u 7c65 -u 9fa4 -u f667 -u e5b6 -u 8bff -u 2b53 -u ff4b"
OFF_DATA="-u 08f0 -u 8030 -u 75b8 -u 27e1 -u fe02 -u 7f55 -u 7d65 -u 9fa4 -u f667 -u d4b6 -u 8bbf -u 2b53 -u ef21"

# URL encode for curl
url_encode() {
    echo "$1" | sed 's/ /%20/g'
}

case "$CMD" in
    bind)   DATA="$BIND_DATA" ; label="🔗 BIND" ;;
    on)     DATA="$ON_DATA"   ; label="💡 ON" ;;
    off)    DATA="$OFF_DATA"  ; label="💡 OFF" ;;
    dim)
        addr=$(printf "0x%08x\n" $((0x$(jq -r '.lu' .env | cut -d- -f2-3 | tr -d -) + 1)))
        DATA=$(./lampctrl -a "$addr" -d "${1:-128},${2:-64}")
        label="🌗 DIM"
        ;;
    *) echo "Usage: $0 <pi-host> bind|on|off|dim [orange] [white]"; exit 1 ;;
esac

ENCODED=$(url_encode "$DATA")
curl -s -X POST "http://$PI:$PORT/broadcast" -d "$ENCODED" && echo " $label → $PI"
