#!/usr/bin/env python3
"""LampSmart Pro web controller — FastAPI backend on port 8003."""

import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

LAMPCTRL = Path(__file__).resolve().parent.parent / "lampctrl.sh"
LAMPS = ["master", "elias", "dining", "living"]

# Track last known state (BLE is one-way, so this is best-effort)
_lamp_state: dict[str, bool] = {l: False for l in LAMPS}

app = FastAPI(title="Lamp Control")


def run_lamp(lamp: str, cmd: str, *args: str) -> tuple[bool, str]:
    """Run lampctrl.sh and return (success, message)."""
    if cmd == "on":
        cargs = ["-o", "1"]
    elif cmd == "off":
        cargs = ["-o", "0"]
    elif cmd == "dim":
        cargs = ["-d", f"{args[0]},{args[1]}"] if len(args) >= 2 else ["-d", "128,64"]
    else:
        return False, f"Unknown command: {cmd}"

    command = [str(LAMPCTRL), "-l", lamp] + cargs
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode == 0:
            if cmd in ("on", "off"):
                _lamp_state[lamp] = (cmd == "on")
            return True, output or f"{lamp} {cmd} OK"
        return False, output or f"Exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


@app.get("/api/lamp/{lamp}/{cmd}")
async def lamp_command(lamp: str, cmd: str, orange: int = 128, white: int = 64):
    if lamp not in LAMPS:
        raise HTTPException(404, f"Unknown lamp: {lamp}")
    if cmd not in ("on", "off", "dim"):
        raise HTTPException(400, f"Unknown command: {cmd}")

    if cmd == "dim":
        ok, msg = run_lamp(lamp, "dim", str(orange), str(white))
    else:
        ok, msg = run_lamp(lamp, cmd)

    return {"ok": ok, "lamp": lamp, "cmd": cmd, "message": msg}


@app.get("/api/lamp/{lamp}")
async def lamp_status(lamp: str):
    if lamp not in LAMPS:
        raise HTTPException(404, f"Unknown lamp: {lamp}")
    return {"on": _lamp_state.get(lamp, False)}


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
