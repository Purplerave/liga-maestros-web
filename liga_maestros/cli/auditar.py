"""Auditar Jornada - re-export from root."""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from AUDITAR_JORNADA_LIGA_MAESTROS import build_audit, render_markdown, main

__all__ = ["build_audit", "render_markdown", "main"]
