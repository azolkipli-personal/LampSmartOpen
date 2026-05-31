#!/usr/bin/python3.13
"""Bridge MQTT → lamp-web HTTP API for Home Assistant."""

import json
import os
import subprocess
import time

import paho.mqtt.client as mqtt

LAMP_API = os.environ.get("LAMP_API", "http://172.17.0.1:8003")
LAMPS = ["master", "living", "dining"]
MQTT_HOST = os.environ.get("MQTT_HOST", "172.17.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))


def api_get(path):
    """Call lamp-web API."""
    try:
        r = subprocess.run(
            ["curl", "-sf", f"{LAMP_API}{path}"],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    for lamp in LAMPS:
        client.subscribe(f"lamp/{lamp}/set")
        client.subscribe(f"lamp/{lamp}/brightness/set")
        client.subscribe(f"lamp/{lamp}/color_temp/set")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    parts = topic.split("/")

    if len(parts) < 2:
        return

    lamp = parts[1]

    if topic.endswith("/set"):
        if payload == "ON":
            api_get(f"/api/lamp/{lamp}/on")
        elif payload == "OFF":
            api_get(f"/api/lamp/{lamp}/off")

    elif topic.endswith("/brightness/set"):
        try:
            brightness = int(float(payload))
            brightness = max(0, min(100, brightness))
            api_get(f"/api/lamp/{lamp}/brightness?value={brightness}")
        except ValueError:
            pass

    elif topic.endswith("/color_temp/set"):
        try:
            ct = int(float(payload))
            ct = max(50, min(400, ct))
            api_get(f"/api/lamp/{lamp}/temperature?value={ct}")
        except ValueError:
            pass


def publish_state(client, lamp):
    """Poll lamp state and publish to MQTT."""
    state = api_get(f"/api/lamp/{lamp}/status")
    if state:
        client.publish(f"lamp/{lamp}/state", "ON" if state.get("on") else "OFF", retain=True)
        client.publish(f"lamp/{lamp}/brightness", str(state.get("brightness", 0)), retain=True)
        client.publish(f"lamp/{lamp}/color_temp", str(state.get("colorTemp", 225)), retain=True)


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.will_set("lamp/bridge/status", "offline", retain=True)

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    print("MQTT → lamp-web bridge started")
    client.publish("lamp/bridge/status", "online", retain=True)

    try:
        while True:
            for lamp in LAMPS:
                publish_state(client, lamp)
            time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        client.publish("lamp/bridge/status", "offline", retain=True)
        client.loop_stop()


if __name__ == "__main__":
    main()
