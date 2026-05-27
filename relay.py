#!/usr/bin/env python3
"""
BLE Proxy Relay for LampSmart Pro lamps
Runs on Raspberry Pi 3B near the lamps.
Receives pre-computed btmgmt advertising payloads from NUC via HTTP,
broadcasts them as BLE advertisements.

Usage: python3 relay.py [--port 8765]
"""

import subprocess, sys, json
from http.server import HTTPServer, BaseHTTPRequestHandler

BTMGMT = "/usr/bin/btmgmt"
INDEX = "0"
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

            # Strip trailing newlines but keep the -u format
            cmd = cmd.strip()

            if not cmd or not cmd.startswith("-u"):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Bad payload: expected btmgmt -u format\n")
                return

            full_cmd = [BTMGMT, "-i", INDEX, "add-adv", "-c", "-g"] + cmd.split() + ["-D", "2", "1"]
            print(f"[relay] broadcasting: {cmd[:60]}...", flush=True)

            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=5)
            status = result.returncode == 0
            print(f"[relay] {'OK' if status else 'FAIL'}: {result.stdout.strip() or result.stderr.strip()}", flush=True)

            self.send_response(200 if status else 500)
            self.end_headers()
            self.wfile.write((result.stdout or result.stderr).encode())

        elif self.path == "/health":
            # Check btmgmt works
            r = subprocess.run([BTMGMT, "-i", INDEX, "info"], capture_output=True, text=True, timeout=3)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"BLE relay alive\n")

        elif self.path == "/ping":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"pong\n")

        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"🔵 BLE Proxy Relay on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), RelayHandler).serve_forever()
