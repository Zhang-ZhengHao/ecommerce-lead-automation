"""Runtime release and build identity shown in the product footer.

The launcher captures the commit before starting Streamlit and passes it in
``COMMERCE_LEAD_BUILD_SHA``.  Capturing it at process start is intentional: an
old process keeps showing the old SHA after a new commit, making stale
deployments visible instead of silently reporting the repository's latest
HEAD.
"""

from __future__ import annotations

import os


APP_VERSION = "0.1.0"


def normalize_build_sha(value: object) -> str:
    """Return a short, printable build id or ``dev`` when unavailable."""

    text = str(value or "").strip()
    return text[:12] if text else "dev"


def format_release_identity(build_sha: object) -> str:
    """Return the public release version paired with its immutable build id."""

    return f"v{APP_VERSION} · build {normalize_build_sha(build_sha)}"


BUILD_SHA = normalize_build_sha(os.getenv("COMMERCE_LEAD_BUILD_SHA"))
