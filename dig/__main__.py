"""Entry point: `python -m dig`."""

from __future__ import annotations

import sys


def main() -> int:
    """Start Dig. The real window arrives in the app-shell phase."""
    from dig import __version__

    print(f"Dig {__version__} — skeleton. The window is not built yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
