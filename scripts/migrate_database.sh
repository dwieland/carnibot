#!/bin/bash

pushd /opt/carnibot
alembic -c /etc/carnibot/alembic.ini upgrade head
popd
