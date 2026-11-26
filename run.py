#!/usr/bin/env python3
"""Command line. Run as `python3 -I run.py <command> ...`.
-I keeps the current folder (and any saved page's folder) off the import path;
only this repository's own folder is added."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from menu_agent.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
