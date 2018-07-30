#!/bin/bash

echo `pwd`
pex -r requirements.txt -D . -o carnibot -m disco.cli
