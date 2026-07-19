#!/usr/bin/env bash
set -euo pipefail

python3 -m unittest discover -s tests
python3 app.py "Explain binary search in simple words" --trace
