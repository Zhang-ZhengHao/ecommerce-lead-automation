#!/usr/bin/env bash
set -euo pipefail

: "${PORT:?PORT is required}"

if [ -d "$(pwd)/pydeps" ]; then
  export PYTHONPATH="$(pwd)/pydeps:${PYTHONPATH:-}"
fi

# Capture the revision once, before handing control to Streamlit.  Do not
# resolve git HEAD inside the app: an old long-lived process must keep showing
# its own SHA after a newer commit lands.
if [ -z "${COMMERCE_LEAD_BUILD_SHA:-}" ]; then
  COMMERCE_LEAD_BUILD_SHA="$(git rev-parse --short=12 HEAD 2>/dev/null || printf 'dev')"
  export COMMERCE_LEAD_BUILD_SHA
fi

exec python3 -m streamlit run app.py \
  --global.developmentMode=false \
  --server.address=0.0.0.0 \
  --server.port="${PORT}" \
  --server.headless=true \
  --server.fileWatcherType=none \
  --browser.gatherUsageStats=false
