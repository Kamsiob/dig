"""Entry point: `python -m dig`."""

from __future__ import annotations

import sys

from dig.app import main

if __name__ == "__main__":
    sys.exit(main())
