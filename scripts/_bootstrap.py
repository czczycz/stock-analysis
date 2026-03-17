"""Common bootstrap for all CLI scripts under scripts/.

Call ``bootstrap()`` at the top of each script to set up UTF-8 IO
and ensure both the project root and scripts/ are on sys.path.
"""

import sys
from pathlib import Path

_BOOTSTRAPPED = False


def bootstrap() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    _BOOTSTRAPPED = True

    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                pass

    root = str(Path(__file__).resolve().parent.parent)
    scripts = str(Path(__file__).resolve().parent)
    for p in (root, scripts):
        if p not in sys.path:
            sys.path.insert(0, p)
