#!/usr/bin/env python3
"""Compatibility dispatch; the implementation belongs to pi-autowork/scripts/wire-owner-cron.py."""
from pathlib import Path
import runpy
import sys

_target = Path(__file__).resolve().parents[1] / 'pi-autowork/scripts/wire-owner-cron.py'
sys.argv[0] = str(_target)
runpy.run_path(str(_target), run_name='__main__')
