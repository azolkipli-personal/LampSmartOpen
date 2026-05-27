#!/bin/bash
# Fast lamp control — on/off/dim
# Usage: ./fast-lamp.sh on|off|dim [orange] [white]
# Pre-computed from UUID in .env

CMD="${1:-on}"

sudo btmgmt -i 0 power on >/dev/null 2>&1
sudo btmgmt -i 0 le on >/dev/null 2>&1

case "$CMD" in
  on)
    sudo btmgmt -i 0 add-adv -c -g -u 08f0 -u 8030 -u 75b8 -u 27e1 -u fe02 -u 7f55 -u 7c65 -u 9fa4 -u f667 -u e5b6 -u 8bff -u 2b53 -u ff4b -D 2 1
    echo "💡 ON"
    ;;
  off)
    sudo btmgmt -i 0 add-adv -c -g -u 08f0 -u 8030 -u 75b8 -u 27e1 -u fe02 -u 7f55 -u 7d65 -u 9fa4 -u f667 -u d4b6 -u 8bbf -u 2b53 -u ef21 -D 2 1
    echo "💡 OFF"
    ;;
  dim)
    # dim needs dynamic computation, fall back to lampctrl
    addr=$(printf "0x%08x\n" $((0x$(jq -r '.lu' .env | cut -d- -f2-3 | tr -d -) + 1)))
    data=$(./lampctrl -a "$addr" -d "${2:-128},${3:-64}")
    sudo btmgmt -i 0 add-adv -c -g $data -D 2 1
    echo "💡 DIM ${2:-128},${3:-64}"
    ;;
  *)
    echo "Usage: $0 on|off|dim [orange] [white]"
    exit 1
    ;;
esac

sleep 1
sudo btmgmt -i 0 clr-adv 2>/dev/null
