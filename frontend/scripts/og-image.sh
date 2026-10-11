#!/bin/sh
# public/og.jpg'yi scripts/og-image.svg'den üretir (macOS: Chrome + sips).
# virtual-time-budget, Chrome'un Google Fonts'u bekleyip öyle çekmesi için.
set -e
cd "$(dirname "$0")/.."
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --hide-scrollbars \
  --virtual-time-budget=4000 \
  --screenshot=shot.png --window-size=1200,630 \
  "file://$PWD/scripts/og-image.svg"
sips -s format jpeg -s formatOptions 82 shot.png --out public/og.jpg
rm shot.png
