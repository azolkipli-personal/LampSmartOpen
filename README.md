# LampSmartOpen

Control LampSmart Pro BLE lamps from Linux — no vendor app, no cloud, just `btmgmt`.

⚠️ Experimental. Use at your own risk.

## What This Repo Contains

- **BLE layer** — `lampctrl.sh` + `lampctrl` C binary for sending BLE commands
- **Per-lamp UUIDs** — `lamps/{name}/.env` for controlling each lamp individually
- **Web UI** — `web/server.py` + frontend for browser control
- **Google Home integration** — Home Assistant + MQTT bridge (free), no subscription needed

## Quick Start

### 1. Install Dependencies

**Fedora:**
```bash
sudo dnf install bluez bluez-tools cmake gcc make jq git python3 python3-pip
```

**Debian / Ubuntu / Raspberry Pi OS:**
```bash
sudo apt update
sudo apt install bluez bluez-tools cmake gcc make jq git python3 python3-pip
```

**Python packages for the web UI:**
```bash
pip install fastapi uvicorn
```

### 2. Clone & Build

```bash
git clone https://github.com/azolkipli-personal/LampSmartOpen.git
cd LampSmartOpen
cmake -S . -B build
cmake --build build
```

Verify:
```bash
./build/lampctrl --help
./lampctrl.sh --help    # should print usage
```

### 3. Get Your Lamp UUIDs

You only need the official LampSmart Pro app **once** to extract per-lamp UUIDs.

1. Open the LampSmart Pro app on your Android phone
2. Go to **lamp settings → Share** (the app has a `buildQrCode` feature)
3. A QR code appears — scan it with Google Lens or any QR reader
4. The decoded text is your lamp's UUID, looks like: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
5. Repeat for each lamp

### 4. Set Up Per-Lamp UUIDs

Create a `.env` file for each lamp inside `lamps/{name}/`:

```bash
mkdir -p lamps/master lamps/living lamps/dining
```

Then create each `.env`:

```bash
echo '{"lu":"your-master-uuid-here"}' > lamps/master/.env
echo '{"lu":"your-living-uuid-here"}' > lamps/living/.env
echo '{"lu":"your-dining-uuid-here"}' > lamps/dining/.env
```

Each UUID uniquely identifies one lamp — when you bind it later, the lamp permanently associates with that UUID.

### 5. Bind Your Lamps

Each lamp must be bound separately. The lamp only listens for bind commands **within ~5 seconds after power-on**.

1. **Turn the lamp OFF** at the wall switch. Wait 10 seconds.
2. Have your terminal ready in the `LampSmartOpen/` directory.
3. **Turn the lamp ON** (flip the switch).
4. **Immediately** run the bind command for that lamp:

```bash
./lampctrl.sh -l master -b 1
```

5. If the lamp **flashes or blinks**, it worked.
6. Repeat for each lamp (`-l living -b 1`, `-l dining -b 1`).

> **Tip:** The `-b 1` argument tells the lamp to bind to the UUID in that lamp's `.env` file. Each bind command must run within ~5 seconds of powering on that specific lamp.

### 6. Control Individual Lamps

```bash
./lampctrl.sh -l master -o 1    # master ON
./lampctrl.sh -l master -o 0    # master OFF
./lampctrl.sh -l living -o 1    # living ON
./lampctrl.sh -l dining -o 1    # dining ON
./lampctrl.sh -l dining -d 128,64   # dining dim (orange=128, white=64)
```

Without `-l`, it reads the root `.env` (controls all lamps bound to that UUID):
```bash
./lampctrl.sh -o 1   # all lamps ON
./lampctrl.sh -o 0   # all lamps OFF
```

## Web UI (Browser Control)

Start the web server:

```bash
python3 web/server.py
```

Open `http://localhost:8003` in your browser. Each lamp shows ON/OFF buttons and a dim slider.

### Systemd Service (Auto-Start)

Create `~/.config/systemd/user/lamp-web.service`:

```ini
[Unit]
Description=LampSmart Pro Web Controller
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/azolkli/LampSmartOpen/web/server.py
Restart=always
RestartSec=5
WorkingDirectory=/home/azolkli/LampSmartOpen/web
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now lamp-web.service
```

## Google Home Integration (Free — No Subscription)

Voice control via Google Home is now handled by **Home Assistant** + **Mosquitto MQTT** + **MQTT bridge**, completely free.

### Architecture

```
Google Home app → Google HomeGraph API
     ↕ (service account auth)
Home Assistant (:8123)
     ↕ (MQTT light entities)
Mosquitto MQTT (:1883)
     ↕ (lamp/{name}/set)
ha/mqtt_bridge.py (systemd user service)
     ↕ (HTTP GET)
lamp-web FastAPI (:8003) → lampctrl.sh → btmgmt → 💡
```

### Components

| Component | Setup |
|-----------|-------|
| **lamp-web** | `web/server.py` on port 8003 (systemd: `lamp-web.service`) |
| **Home Assistant** | Docker, `ghcr.io/home-assistant/home-assistant:stable`, port 8123 |
| **Mosquitto MQTT** | Docker, `eclipse-mosquitto:2`, port 1883, anonymous auth |
| **MQTT Bridge** | `ha/mqtt_bridge.py` (systemd: `lamp-mqtt-bridge.service`) |

### Setup Steps

1. **HA + MQTT stack** — see `ha/` directory for config examples
2. **Google Cloud Project** — create project, enable HomeGraph API, create service account with JSON key
3. **HA config** — add `google_assistant:` section in `configuration.yaml` (see `ha/configuration.yaml.example`)
4. **Google Home Developer Console** — create Cloud-to-Cloud integration, set OAuth URLs
5. **Link Google Home** — Google Home app → + → Works with Google Home → link project

### HA MQTT Light Config

Each lamp is a MQTT light entity in HA with full brightness + color temperature support:

```yaml
mqtt:
  light:
    - name: "Master Lamp"
      state_topic: "lamp/master/state"
      command_topic: "lamp/master/set"
      brightness_state_topic: "lamp/master/brightness"
      brightness_command_topic: "lamp/master/brightness/set"
      color_temp_state_topic: "lamp/master/color_temp"
      color_temp_command_topic: "lamp/master/color_temp/set"
      brightness_scale: 100
      min_mireds: 50
      max_mireds: 400
```

The MQTT bridge polls lamp-web every 3s and publishes state to retained MQTT topics.

### Google Home Voice Commands

Once linked, you can say:
- *"Hey Google, turn on/off master lamp"*
- *"Hey Google, set living lamp to 50%"*
- *"Hey Google, make dining lamp warmer/cooler"*

### Exposing HA Externally (Required for OAuth Linking)

HA must be accessible via HTTPS for the Google Home OAuth linking flow. Free option: **Tailscale Funnel**.

```bash
sudo tailscale funnel --bg 8123
```

→ HA available at `https://<hostname>.tail<XXXXX>.ts.net` (permanent, HTTPS, free).

### Troubleshooting

If your lamp turns ON from the physical remote but then turns OFF after a few seconds, it's **stale BLE advertisements**.

**What happens:** Each `lampctrl.sh` command adds a BLE advertising instance with `btmgmt add-adv`. If you don't clear it after the command, the instance keeps broadcasting the last command (OFF) every ~100ms. The lamp receives it and reverts.

**The fix** is already in `lampctrl.sh` — `clr-adv` runs before and after each command:

```bash
sudo btmgmt --index 0 clr-adv      # clear any stale ads
sudo btmgmt --index 0 add-adv ...   # send command
sleep 0.1
sudo btmgmt --index 0 clr-adv      # clean up after
```

If you're writing your own scripts, always call `clr-adv` before and after `add-adv`.

## API Reference (Web UI)

| Endpoint | Description |
|---------|-------------|
| `GET /` | Web UI |
| `GET /api/lamp/{name}/on` | Turn lamp on |
| `GET /api/lamp/{name}/off` | Turn lamp off |
| `GET /api/lamp/{name}/dim?orange=128&white=64` | Dim lamp (direct channel control) |
| `GET /api/lamp/{name}/brightness?value=N` | Set brightness 0-100% (HTTP-LIGHTBULB) |
| `GET /api/lamp/{name}/temperature?value=N` | Set color temp 50-400 mired (HTTP-LIGHTBULB) |
| `GET /api/lamp/{name}/status` | Full lamp state `{on, brightness, colorTemp}` |
| `GET /api/lamp/{name}` | Basic lamp state (backward compat) |
| `GET /api/status` | Health check |

## Files in This Repo

| File | Purpose |
|------|---------|
| `lampctrl.sh` | Main control script — `-l <name>` for per-lamp, `-o 1\|0` on/off, `-d O,W` dim, `-b N` bind |
| `main.c` | C source for `lampctrl` binary — builds the BLE command payload |
| `opencodeV3/` | Submodule — the V3 protocol encoder library |
| `build/lampctrl` | Compiled binary |
| `lamps/{name}/.env` | Per-lamp UUID files — one per lamp |
| `web/server.py` | FastAPI web server (port 8003) |
| `web/static/index.html` | Web UI frontend |
| `ha/mqtt_bridge.py` | MQTT → lamp-web HTTP bridge for Home Assistant |
| `ha/configuration.yaml.example` | Home Assistant config example |
| `compute-packets.sh` | Regenerates pre-computed packets (for multi-lamp mode without `-l`) |
| `fast-bind.sh` | Pre-computed bind (single-lamp mode) |
| `fast-lamp.sh` | Pre-computed on/off/dim (single-lamp mode) |
| `relay.py` | Optional: HTTP-to-BLE relay server for range extension (run on a Pi) |
| `pi-setup.sh` | Optional: one-shot setup script for the relay Pi |
| `ble-relay.service` | Optional: systemd unit for auto-starting the relay |
| `send-relay.sh` | Optional: sends commands to a relay Pi instead of local btmgmt |

## License

GNU General Public License v3.0.

This is a fork of **[AuroraRAS/LampSmartOpen](https://github.com/AuroraRAS/LampSmartOpen)**. All credit for the protocol reverse-engineering and the core `lampctrl` C implementation goes to AuroraRAS.
