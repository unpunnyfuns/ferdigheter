#!/usr/bin/env python3
"""Validate skills under skills/ and build index.json plus the CATALOG.md table."""

from __future__ import annotations

import sys

from ferdigheter.cli import main

if __name__ == "__main__":
    sys.exit(main())
