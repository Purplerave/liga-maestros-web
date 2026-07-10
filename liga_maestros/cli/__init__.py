"""Importar Programa Jornada - re-export from root."""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from IMPORTAR_PROGRAMA_JORNADA import import_jornada, main

__all__ = ["import_jornada", "main"]
