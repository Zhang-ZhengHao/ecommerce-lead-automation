"""Runtime build identity shown in the product footer.

The launcher captures the commit before starting Streamlit and passes it in
``COMMERCE_LEAD_BUILD_SHA``.  Capturing it at process start is intentional: an
old process keeps showing the old SHA after a new commit, making stale
deployments visible instead of silently reporting the repository's latest
HEAD.
"""

from __future__ import annotations

import os


def normalize_build_sha(value: object) -> str:
    """Return a short, printable build id or ``dev`` when unavailable."""

    text = str(value or "").strip()
    return text[:12] if text else "dev"


BUILD_SHA = normalize_build_sha(os.getenv("COMMERCE_LEAD_BUILD_SHA"))
