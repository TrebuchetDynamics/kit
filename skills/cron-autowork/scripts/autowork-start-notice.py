#!/usr/bin/env python3
"""Source compatibility entry; profiles receive the standalone component payload."""
from pathlib import Path as _Path

_source = _Path(__file__).resolve().parents[3] / 'pi-autowork/scripts/autowork-start-notice.py'
exec(compile(_source.read_bytes(), str(_source), 'exec'), globals())
