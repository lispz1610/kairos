"""Torna importáveis os pacotes do projeto localizados em ``src/`` nos testes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
