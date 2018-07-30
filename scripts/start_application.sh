#!/bin/bash

python -m disco.cli --config /etc/carnibot.json &
echo $! > /var/run/carnibot.pid
