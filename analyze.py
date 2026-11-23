#!/usr/bin/env python3
"""Backward-compatible entry point: `python analyze.py [--budget N] [--risk-profile P] [--years Y]`.

Equivalent to `python -m src.main analyze ...`.
"""

from __future__ import annotations

import sys

from src.main import main

if __name__ == "__main__":
    raise SystemExit(main(["analyze", *sys.argv[1:]]))
