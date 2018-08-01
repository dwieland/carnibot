#!/bin/sh

cd /opt/carnibot
alembic -c /etc/carnibot/alembic.ini upgrade head
