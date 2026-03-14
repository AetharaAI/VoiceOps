#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <blue|green>"
  exit 1
fi

COLOR="$1"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET_DIR="/etc/nginx/snippets"
TARGET_FILE="$TARGET_DIR/voiceops_active_upstream.conf"

case "$COLOR" in
  blue)
    SRC="$REPO_ROOT/infra/nginx/voiceops-upstream-blue.conf"
    ;;
  green)
    SRC="$REPO_ROOT/infra/nginx/voiceops-upstream-green.conf"
    ;;
  *)
    echo "Color must be 'blue' or 'green'"
    exit 1
    ;;
esac

sudo mkdir -p "$TARGET_DIR"
sudo cp "$SRC" "$TARGET_FILE"
sudo nginx -t
sudo systemctl reload nginx

echo "Switched voiceops upstream to: $COLOR"
