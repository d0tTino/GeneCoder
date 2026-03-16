#!/usr/bin/env python3
"""Fail when generated strategy sections drift from docs/strategy_model.yaml."""

from __future__ import annotations

import sys

from render_strategy_docs import main


if __name__ == "__main__":
    sys.exit(main())
