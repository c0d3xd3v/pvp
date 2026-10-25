#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}" python3 -m pvp "$@"
