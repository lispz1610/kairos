from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from src.core.domain.models import CurationList

FIXTURES_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG_PATH = FIXTURES_DIR / "catalog.json"


def load_mock_catalog(
    path: Optional[Path | str] = None,
) -> Dict[str, List[CurationList]]:
    """Carrega o catálogo de curadoria e POIs a partir de arquivo JSON estruturado."""
    target_path = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    with open(target_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    catalog: Dict[str, List[CurationList]] = {}
    for city, lists in raw_data.items():
        catalog[city] = [CurationList.model_validate(cl) for cl in lists]
    return catalog
