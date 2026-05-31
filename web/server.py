#!/usr/bin/env python3
"""LampSmart Pro web controller — FastAPI backend on port 8003."""

import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

LAMPCTRL = Path(__file__).resolve().parent.parent / "lampctrl.sh"
LAMPS = ["master", "elias", "dining", "living"]

# Track last known state (BLE is one-way, so this is best-effort)
# brightness: 0-100 (percent), colorTemp: 50-400 (mired)
_DEFAULT_STATE = {"on": False, "brightness": 50, "colorTemp": 225}
_lamp_state: dict[str, dict] = {l: dict(_DEFAULT_STATE) for l in LAMPS}

# BLE watchdog state
_ble_error_count = 0
_ble_last_reset = 0.0

app = FastAPI(title="Lamp Control")


def _ble_reset() -> bool:
    """Reset BLE adapter via btmgmt. Returns True if successful."""
    global _ble_last_reset
    try:
        subprocess.run(
            ["sudo", "btmgmt", "power", "off"],
            capture_output=True, timeout=5,
        )
        time.sleep(0.5)
        result = subprocess.run(
            ["sudo", "btmgmt", "power", "on"],
            capture_output=True, timeout=10,
        )
        ok = result.returncode == 0
        _ble_last_reset = time.time()
        return ok
    except Exception:
        return False


def _dim_to(lamp: str, brightness: int, mired: int) -> tuple[bool, str]:
    """Map brightness% + mired to orange/white channels and send."""
    temp_ratio = (mired - 50) / 350  # 0=cool, 1=warm
    orange = round(brightness / 100 * temp_ratio * 255)
    white = round(brightness / 100 * (1 - temp_ratio) * 255)
    orange = max(0, min(255, orange))
    white = max(0, min(255, white))
    return run_lamp(lamp, "dim", str(orange), str(white))


def run_lamp(lamp: str, cmd: str, *args: str) -> tuple[bool, str]:
    """Run lampctrl.sh with BLE watchdog auto-recovery."""
    global _ble_error_count

    def _exec() -> tuple[int, str]:
        command = [str(LAMPCTRL), "-l", lamp] + cargs
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=20,
            )
            output = (result.stdout + result.stderr).strip()
            return result.returncode, output
        except subprocess.TimeoutExpired:
            return -1, "Command timed out"
        except Exception as e:
            return -1, str(e)

    # Build args
    if cmd == "on":
        s = _lamp_state[lamp]
        if s["brightness"] > 0:
            # Send on command first, then restore brightness/temp
            ok, msg = run_lamp(lamp, "_on_raw")
            if ok:
                time.sleep(0.3)
                ok, msg = _dim_to(lamp, s["brightness"], s["colorTemp"])
            return ok, msg
        cargs = ["-o", "1"]  # fallback: simple on
    elif cmd == "_on_raw":
        cargs = ["-o", "1"]  # raw on without dim redirect
    elif cmd == "off":
        cargs = ["-o", "0"]
    elif cmd == "dim":
        cargs = ["-d", f"{args[0]},{args[1]}"] if len(args) >= 2 else ["-d", "128,64"]
    elif cmd == "night":
        cargs = ["-n"]
    else:
        return False, f"Unknown command: {cmd}"

    # First attempt
    retcode, output = _exec()
    is_busy = "Busy" in output or "busy" in output or retcode == -1

    # Retry with BLE reset if busy
    if retcode != 0 and is_busy and _ble_error_count < 3:
        _ble_error_count += 1
        _ble_reset()
        time.sleep(1)
        retcode, output = _exec()
    elif retcode == 0:
        _ble_error_count = 0

    # Process result
    if retcode == 0:
        if cmd in ("on", "night"):
            _lamp_state[lamp]["on"] = True
        elif cmd == "off":
            _lamp_state[lamp]["on"] = False
        elif cmd == "dim":
            _lamp_state[lamp]["on"] = True
            orange = int(args[0])
            white = int(args[1])
            total = orange + white
            if total > 0:
                r = orange / total
                _lamp_state[lamp]["colorTemp"] = round(50 + r * 350)
                _lamp_state[lamp]["brightness"] = round(total / 255 * 100)
        return True, output or f"{lamp} {cmd} OK"
    return False, output or f"Exit code {retcode}"


# ── Specific routes FIRST (before generic {lamp}/{cmd}) ──


@app.get("/api/lamp/{lamp}/brightness")
async def set_brightness(lamp: str, value: int):
    """Set brightness 0-100%. 0 = off."""
    if lamp not in LAMPS:
        raise HTTPException(404, f"Unknown lamp: {lamp}")
    if not 0 <= value <= 100:
        raise HTTPException(400, "Brightness must be 0-100")
    state = _lamp_state[lamp]
    state["brightness"] = value
    if value == 0:
        ok, msg = run_lamp(lamp, "off")
    else:
        state["on"] = True
        ok, msg = _dim_to(lamp, value, state["colorTemp"])
    return {"ok": ok, "lamp": lamp, "brightness": value, "message": msg}


@app.get("/api/lamp/{lamp}/temperature")
async def set_temperature(lamp: str, value: int):
    """Set color temperature 50-400 mired (50=cool, 400=warm)."""
    if lamp not in LAMPS:
        raise HTTPException(404, f"Unknown lamp: {lamp}")
    if not 50 <= value <= 400:
        raise HTTPException(400, "Color temperature must be 50-400 mired")
    state = _lamp_state[lamp]
    state["colorTemp"] = value
    state["on"] = True
    ok, msg = _dim_to(lamp, state["brightness"], value)
    return {"ok": ok, "lamp": lamp, "colorTemp": value, "message": msg}


@app.get("/api/lamp/{lamp}/status")
async def lamp_status_full(lamp: str):
    """Full status for Homebridge lightbulb polling."""
    if lamp not in LAMPS:
        raise HTTPException(404, f"Unknown lamp: {lamp}")
    return dict(_lamp_state[lamp])


# ── Generic lamp command route ──


@app.get("/api/lamp/{lamp}/{cmd}")
async def lamp_command(lamp: str, cmd: str, orange: int = 128, white: int = 64):
    if lamp not in LAMPS:
        raise HTTPException(404, f"Unknown lamp: {lamp}")
    if cmd not in ("on", "off", "dim", "night"):
        raise HTTPException(400, f"Unknown command: {cmd}")
    if cmd == "dim":
        ok, msg = run_lamp(lamp, "dim", str(orange), str(white))
    else:
        ok, msg = run_lamp(lamp, cmd)
    return {"ok": ok, "lamp": lamp, "cmd": cmd, "message": msg}


@app.get("/api/lamp/{lamp}")
async def lamp_status_basic(lamp: str):
    """Basic status (backward compat with old Homebridge HTTP-SWITCH)."""
    if lamp not in LAMPS:
        raise HTTPException(404, f"Unknown lamp: {lamp}")
    return dict(_lamp_state[lamp])


@app.get("/api/status")
async def status():
    return {"lamps": LAMPS, "healthy": True}


# Serve static frontend
FRONTEND = Path(__file__).parent / "static"
FRONTEND.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
