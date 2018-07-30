#!/bin/bash

if [ -e "/var/run/carnibot.pid" ]; then
  cat /var/run/carnibot.pid | xargs kill -TERM
fi
