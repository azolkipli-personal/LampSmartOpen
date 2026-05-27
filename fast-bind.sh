#!/bin/bash
# fast-bind.sh — instant lamp binding, pre-computed from UUID in .env
# Power-cycle the lamp, then run: ./fast-bind.sh
# Sends the bind packet within ~0.5s of execution, not 5s.

sudo btmgmt -i 0 power on >/dev/null 2>&1
sudo btmgmt -i 0 le on >/dev/null 2>&1
sudo btmgmt -i 0 add-adv -c -g -u 08f0 -u 8030 -u 75b8 -u 27e1 -u fe02 -u 7f55 -u 4465 -u 9fa4 -u f667 -u 57b6 -u 8bd0 -u 2b53 -u 2b9f -D 2 1
echo "✅ BIND SENT"
sleep 1
sudo btmgmt -i 0 clr-adv 2>/dev/null
