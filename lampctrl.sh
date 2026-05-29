#!/bin/bash
# lampctrl.sh — Control LampSmart Pro BLE lamps
# Reads UUID from .env (single lamp) or lamps/<name>/.env (per-lamp),
# generates BLE advertising data via lampctrl binary, broadcasts via btmgmt.
#
# Usage:
#   ./lampctrl.sh -l master -o 1      # master on
#   ./lampctrl.sh -l dining -o 0      # dining off
#   ./lampctrl.sh -l living -d 128,64 # living dim
#   ./lampctrl.sh -o 1                # single-lamp mode (root .env)

DIR="$(cd "$(dirname "$0")" && pwd)"
LAMPCTRL="$DIR/build/lampctrl"
ENV_FILE="$DIR/.env"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -l NAME       Lamp name (master, living, dining, elias).
                Reads UUID from lamps/<NAME>/.env.
                Omit for single-lamp mode (root .env).
  -i IDX        Bluetooth adapter index (default: 0)
  -d O,W        Dimming mode, orange and white values, e.g. -d 128,64
  -n            Night dimming mode
  -b N          Binding mode, e.g. -b 1
  -o 0|1        Lamp on/off, e.g. -o 1 (on), -o 0 (off)
  -h            Show this help message

EOF
}

IDX=0
LAMP_NAME=""
declare -a lamp_args=()

while getopts ":l:i:d:nb:o:h" opt; do
    case "$opt" in
        l) LAMP_NAME="$OPTARG" ;;
        i) IDX="$OPTARG" ;;
        d) lamp_args=(-d "$OPTARG") ;;
        n) lamp_args=(-n) ;;
        b) lamp_args=(-b "$OPTARG") ;;
        o) lamp_args=(-o "$OPTARG") ;;
        h) usage; exit 0 ;;
        :) echo "Error: -$OPTARG requires an argument." >&2; usage; exit 1 ;;
        \?) echo "Error: Unknown option -$OPTARG" >&2; usage; exit 1 ;;
    esac
done
shift $((OPTIND - 1))

if [ "${#lamp_args[@]}" -eq 0 ]; then
    echo "Error: No command specified. Use one of -d, -n, -b, or -o." >&2
    usage; exit 1
fi

# --- Resolve UUID ---
if [ -n "$LAMP_NAME" ]; then
    ENV_FILE="$DIR/lamps/$LAMP_NAME/.env"
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found." >&2
    exit 1
fi

uuid=$(jq -r '.lu' "$ENV_FILE")
if [ -z "$uuid" ] || [ "$uuid" = "null" ]; then
    echo "Error: Key \"lu\" not found in $ENV_FILE." >&2
    exit 1
fi

# UUID: 89815eb1-27c7-500e-9d7f-d147a47ce477 → "27c7-500e" → 0x27c7500e + 1
hex=$(echo "$uuid" | cut -d- -f2-3 | tr -d -)
if ! [[ "$hex" =~ ^[0-9a-fA-F]+$ ]]; then
    echo "Error: Invalid hex from UUID: $hex" >&2
    exit 1
fi
addr=$(printf "0x%08x\n" $(( 0x$hex + 1 )))

# --- Generate advertising data ---
if [ ! -x "$LAMPCTRL" ]; then
    echo "Error: lampctrl binary not found at $LAMPCTRL" >&2
    exit 1
fi

adv_data=$("$LAMPCTRL" -a "$addr" "${lamp_args[@]}")

# --- Broadcast via btmgmt ---
sudo btmgmt --index "$IDX" power on 2>/dev/null
sudo btmgmt --index "$IDX" le on 2>/dev/null
sleep 0.1
sudo btmgmt --index "$IDX" clr-adv 2>/dev/null
sudo btmgmt --index "$IDX" add-adv -c -g $adv_data -D 2 1
sleep 0.1
sudo btmgmt --index "$IDX" clr-adv 2>/dev/null
sudo btmgmt --index "$IDX" le off 2>/dev/null || true

echo "OK → ${LAMP_NAME:-single} $*"
