#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

pyside6-rcc resources/resources.qrc -o resources/resources.py
python3 pvp.py "$@"
