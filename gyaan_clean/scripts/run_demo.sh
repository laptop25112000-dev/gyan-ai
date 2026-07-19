#!/usr/bin/env bash
set -euo pipefail

python3 app.py "What is the latest news about AI models?" --trace
echo
python3 app.py "Write Python code for a simple calculator" --trace
