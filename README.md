# LampSmartOpen

> Control LampSmart Pro BLE lamps from Linux — no vendor app, no cloud, just `btmgmt`.
>
> **This fork** adds instant pre-computed control scripts, the QR code UUID extraction method, and a network relay mode for range extension.
>
> ⚠️ Experimental. Use at your own risk.

---

## Step 0: What You Need

* A **Linux machine** with a BLE adapter (built-in or USB dongle)
* One or more **LampSmart Pro** compatible lamps
* An **Android phone** with the LampSmart Pro app installed (just once, to get the UUID)
* **sudo** access on the Linux machine

---

## Step 1: Install Dependencies

**Fedora:**
```bash
sudo dnf install bluez bluez-tools cmake gcc make jq git
```

**Debian / Ubuntu / Raspberry Pi OS:**
```bash
sudo apt update
sudo apt install bluez bluez-tools cmake gcc make jq git
```

**Verify your BLE adapter works:**
```bash
sudo btmgmt info
```
You should see something like:
```
hci0:   Primary  Bus: USB
        BD Address: XX:XX:XX:XX:XX:XX
        settings: powered ssp br/edr le ...
```

---

## Step 2: Clone and Build

```bash
git clone --recurse-submodules https://github.com/azolkipli-personal/LampSmartOpen.git
cd LampSmartOpen
cmake -S . -B build
cmake --build build
```

This produces the `build/lampctrl` binary. Test it:
```bash
./build/lampctrl --help
```

---

## Step 3: Get Your Lamp UUID

The LampSmart Pro app stores a per-lamp UUID. You need this to generate commands. **You only need the app once** — after extracting the UUID, you never need it again.

### Method A: QR Code (easiest)

1. Open the **LampSmart Pro** app on your Android phone
2. Make sure the lamp is paired in the app
3. Navigate to **lamp settings → Share** (the app has a built-in `buildQrCode` feature)
4. The app displays a **QR code** on screen
5. Scan it with **Google Lens** or any QR code reader
6. The decoded text contains your lamp's UUID — it looks like:
   ```
   XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
   ```
7. Copy it. That's your `lu` value for the next step.

> **Evidence**: The app's decompiled native code (`libapp.so`) contains `buildQrCode`, `deviceId`, and QR-sharing UI strings in Indonesian, Malay, Spanish, and Chinese — confirming this feature ships in the official app.

### Method B: Already have a UUID?

If a friend already set this up, or you extracted it previously, just re-use the UUID:
```
{"lu":"ac194b5e-0a95-50e5-a3f5-c9571988bff5"}
```
All your lamps bind to the same UUID — they're distinguished by the binding timing, not different UUIDs.

---

## Step 4: Configure `.env`

Create your `.env` file with the UUID from Step 3:
```bash
echo '{"lu":"YOUR-UUID-HERE"}' > .env
```

Example:
```bash
echo '{"lu":"ac194b5e-0a95-50e5-a3f5-c9571988bff5"}' > .env
```

**Verify:**
```bash
cat .env
```
Should show your UUID.

---

## Step 5: Generate Pre-Computed Packets

This fork uses pre-computed BLE advertising data for speed (0.15s vs ~5s). Generate them now:

```bash
./compute-packets.sh
```

This reads `.env`, derives the control address, and stores the packets inline in `fast-bind.sh` and `fast-lamp.sh`. If you change your UUID later, re-run this step.

---

## Step 6: Bind Your Lamp

This is the most finicky part. The lamp only listens for a bind command **within ~5 seconds after power-on**.

### The binding dance

1. **Turn the lamp OFF** at the wall switch (or unplug it). Wait 10 seconds.
2. **Prepare to run the command** — have your terminal open in the `LampSmartOpen/` directory.
3. **Turn the lamp ON** (plug it back in or flip the switch).
4. **Immediately** run:
   ```bash
   ./fast-bind.sh
   ```
   You should see `✅ BIND SENT` within a fraction of a second.
5. If the lamp **flashes or blinks**, it worked — the lamp is now paired to your UUID.

### Troubleshooting binding

| Problem | Fix |
|---------|-----|
| Nothing happens | Wait a full 10s with lamp OFF before powering on. The bind window is very short. |
| `clr-adv` error | Harmless. The `add-adv` line is what matters — look for `Instance added: 1`. |
| Lamp doesn't flash | The BLE adapter might not reach. Move the Linux machine closer, or use the relay mode below. |
| `sudo` prompts | The scripts call `sudo btmgmt` internally. If you get password prompts, run `sudo -v` first. |

---

## Step 7: Control Your Lamp

Once bound, control is instant:

```bash
./fast-lamp.sh on          # Turn on
./fast-lamp.sh off         # Turn off
./fast-lamp.sh dim 128 64  # Dim: 0-255 orange, 0-255 white
```

Each command sends a single BLE advertising burst and exits. No daemon, no background process, no pair-and-connect dance.

---

## Step 8: Bind More Lamps

All your lamps share the same UUID from `.env`. To bind additional lamps:

1. Leave `.env` as-is (same UUID)
2. Power-cycle the NEXT lamp
3. Run `./fast-bind.sh` within 5 seconds
4. Verify with `./fast-lamp.sh on` → `./fast-lamp.sh off`

Repeat for each lamp. After binding all of them, `./fast-lamp.sh on` turns **all lamps on simultaneously**.

---

## Step 9 (Optional): Network Relay for Distant Lamps

If some lamps are out of BLE range, run a relay on a **Raspberry Pi** (or any Linux box) placed closer to the lamps.

### Set up the relay

1. SSH into the Pi: `ssh pi@pi3b.local`
2. Run the one-shot setup:
   ```bash
   curl -sL https://raw.githubusercontent.com/azolkipli-personal/LampSmartOpen/main/pi-setup.sh | bash
   ```
3. Reboot: `sudo reboot`

The Pi now runs `relay.py` as a systemd service, listening on port 8765.

### Send commands via relay

From your main Linux machine:
```bash
./send-relay.sh pi3b.local on
./send-relay.sh pi3b.local off
./send-relay.sh pi3b.local bind
./send-relay.sh pi3b.local dim 128 64
```

The flow: your machine → HTTP POST → Pi → `btmgmt` BLE broadcast → lamps.

---

## How It Works

The original LampSmart Pro Android app doesn't maintain a GATT connection. Instead, it broadcasts **BLE advertising packets** with encoded commands. The lamp listens passively and acts on matching packets.

LampSmartOpen reconstructs this:

1. `.env` stores your lamp UUID
2. The shell scripts extract UUID fields, derive a **32-bit control address**, and pass it to `lampctrl`
3. `lampctrl` (C binary, using the `opencodeV3` library) encodes the command into a BLE advertising payload
4. `btmgmt add-adv` broadcasts that payload briefly
5. The lamp receives it and executes the command (on/off/dim/bind)

All in one burst with no persistent connection. That's why commands are instant, and why binding requires the 5-second power-cycle window — the lamp only watches for bind packets right after boot.

---

## Files in This Repo

| File | Purpose |
|------|---------|
| `main.c` | C source for `lampctrl` — builds the BLE command payload |
| `opencodeV3/` | Submodule — the V3 protocol encoder library |
| `lampctrl.sh` | Upstream wrapper: computes address + fires command (~5s) |
| `fast-bind.sh` | ⚡ Pre-computed bind — fires in ~0.15s |
| `fast-lamp.sh` | ⚡ Pre-computed on/off/dim — instant |
| `compute-packets.sh` | Regenerates pre-computed packets from `.env` |
| `relay.py` | HTTP → BLE relay server (run on a Pi near lamps) |
| `send-relay.sh` | Sends commands to a relay from your main machine |
| `pi-setup.sh` | One-shot Pi configuration |
| `ble-relay.service` | Systemd unit for auto-starting relay on boot |
| `.env` | Your lamp UUID (JSON format) |
| `LICENSE` | GPL-3.0 |

---

## 🔗 Upstream and Credits

This is a fork of **[AuroraRAS/LampSmartOpen](https://github.com/AuroraRAS/LampSmartOpen)** (GPL-3.0).

All credit for the **protocol reverse-engineering** and the core `lampctrl` C implementation goes to **AuroraRAS**. This project would not exist without their work.

The `opencodeV3` submodule (also by AuroraRAS) implements the V3 LampSmart Pro encoding.

### What this fork adds

* **Speed**: Pre-computed packets reduce command latency from ~5s to ~0.15s
* **Discovery**: Documented the QR code method for extracting UUID from the official app
* **Relay mode**: HTTP-to-BLE relay for range extension via any Linux box
* **Step-by-step guide**: Ground-up walkthrough tested on Fedora and Raspberry Pi OS
* **Pi setup automation**: One-command deployment script + systemd service

---

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).

---

# LampSmartOpen（日本語）

LampSmartOpenは**LampSmart Pro**の制御ロジックをオープンソースで再実装したプロジェクトです。
Linuxマシンから`btmgmt`などの標準ツールだけでBLEランプを制御でき、ベンダーのAndroidアプリやクラウドは不要です。

## クイックスタート

```bash
# 1. 依存関係インストール
sudo apt install bluez bluez-tools cmake gcc make jq git

# 2. ビルド
git clone --recurse-submodules https://github.com/azolkipli-personal/LampSmartOpen.git
cd LampSmartOpen
cmake -S . -B build && cmake --build build

# 3. UUIDを.envに設定（アプリのQRコードから取得）
echo '{"lu":"あなたのUUID"}' > .env

# 4. パケット生成
./compute-packets.sh

# 5. ランプをバインド（電源ONから5秒以内）
./fast-bind.sh

# 6. 制御
./fast-lamp.sh on
./fast-lamp.sh off
./fast-lamp.sh dim 128 64
```

## UUIDの取得方法

LampSmart Proアプリには`buildQrCode`機能があり、ランプ設定→共有からQRコードを表示できます。Google LensでスキャンしてUUIDを取得し、`.env`に設定してください。

## 仕組み

LampSmart ProアプリはGATT接続ではなく、**BLE Advertisingパケット**でコマンドを送信します。LampSmartOpenはこの動作を再現し、UUIDから制御アドレスを生成→`lampctrl`でペイロード生成→`btmgmt`でブロードキャスト、という流れでランプを制御します。

## アップストリーム

**[AuroraRAS/LampSmartOpen](https://github.com/AuroraRAS/LampSmartOpen)**（GPL-3.0）のフォークです。プロトコル解析とCコア実装の全ての功績はAuroraRASに帰属します。

## ライセンス

GNU General Public License v3.0
