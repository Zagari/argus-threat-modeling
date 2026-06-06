"""Coloca `training/` no sys.path para os testes importarem os módulos do dataset."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
