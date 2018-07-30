#!/bin/bash

echo `pwd`
pex -r requirements.txt -D . -o /usr/local/bin/carnibot -m disco.cli
