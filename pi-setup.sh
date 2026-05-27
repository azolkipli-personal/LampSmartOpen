#!/bin/bash
# pi-setup.sh — one-shot configuration for Raspberry Pi 3B BLE relay
# Run this ON THE PI after first boot and SSH in.
# Usage: ssh pi@pi3b.local 'bash -s' < pi-setup.sh

set -e

echo "🔧 Setting up BLE Proxy Relay on Pi 3B..."

# 1. Install dependencies
sudo apt update
sudo apt install -y pi-bluetooth bluez bluez-tools python3

# 2. Ensure Bluetooth is up
sudo systemctl enable bluetooth
sudo systemctl restart bluetooth
sudo btmgmt power on
sudo btmgmt le on
sudo btmgmt bredr off

echo "✅ Bluetooth: $(sudo btmgmt info | head -1)"

# 3. Allow btmgmt without sudo (add pi to bluetooth group)
sudo usermod -aG bluetooth pi

# 4. Create relay script
cat > /home/pi/relay.py << 'PYEOF'
#!/usr/bin/env python3
import subprocess, sys, json
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8765

class RelayHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[relay] {args[0] if args else fmt}", flush=True)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)

        if self.path == "/broadcast":
            try:
                data = json.loads(payload)
                cmd = data.get("cmd", "")
            except:
                cmd = payload.decode()
            cmd = cmd.strip()

            if not cmd or not cmd.startswith("-u"):
                self.send_response(400); self.end_headers()
                self.wfile.write(b"Bad payload\n"); return

            full_cmd = ["sudo", "btmgmt", "-i", "0", "add-adv", "-c", "-g"] + cmd.split() + ["-D", "2", "1"]
            print(f"[relay] broadcasting: {cmd[:60]}...", flush=True)
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=5)
            status = result.returncode == 0
            print(f"[relay] {'OK' if status else 'FAIL'}: {result.stdout.strip() or result.stderr.strip()}", flush=True)
            self.send_response(200 if status else 500); self.end_headers()
            self.wfile.write((result.stdout or result.stderr).encode())
        elif self.path in ("/health", "/ping"):
            self.send_response(200); self.end_headers()
            self.wfile.write(b"BLE relay alive\n")
        else:
            self.send_response(404); self.end_headers()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"BLE Proxy Relay on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), RelayHandler).serve_forever()
PYEOF

chmod +x /home/pi/relay.py

# 5. Install systemd service
sudo tee /etc/systemd/system/ble-relay.service > /dev/null << 'SVCEOF'
[Unit]
Description=BLE Proxy Relay for LampSmart Pro
After=bluetooth.target network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/pi/relay.py
Restart=always
RestartSec=5
User=pi
WorkingDirectory=/home/pi

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable ble-relay
sudo systemctl start ble-relay

echo ""
echo "✅ Pi BLE Proxy setup complete!"
echo "   Test: curl http://$(hostname -I | awk '{print $1}'):8765/ping"
echo ""
sleep 1
sudo systemctl status ble-relay --no-pager | head -8
