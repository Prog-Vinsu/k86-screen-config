#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
python3 "$DIR/k86_gif_uploader.py" "$@"
