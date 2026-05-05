#!/usr/bin/env python
"""Convenience launcher: run the bot from a checkout without installing the package."""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

from ukrainability_telegram_bot.cli import main

if __name__ == "__main__":
    main()
