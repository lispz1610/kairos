from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, List, Optional

from src.adapters.places.offline_adapter import OfflineReplayPlacesAdapter
from src.core.domain.models import POI, Coordinates, CurationList
from src.core.ports.places import PlacesPort


class CachedPlacesAdapter(PlacesPort):
    """Adaptador de lugares com padrão Cache-Aside persistido em SQLite (ADR 0003 e ADR 0005)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_path: Optional[Path | str] = None,
        fallback_adapter: Optional[PlacesPort] = None,
    ) -> None:
        """Inicializa o cache SQLite e o fallback Offline Replay da Porta PlacesPort."""
        self.api_key = api_key if api_key is not None else os.getenv("GOOGLE_MAPS_API_KEY")
        self.cache_path = str(cache_path) if cache_path is not None else "cache/places_cache.db"
        self.fallback_adapter = fallback_adapter or OfflineReplayPlacesAdapter()
        self._init_db()

    def _init_db(self) -> None:
        if self.cache_path != ":memory:":
            Path(self.cache_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.cache_path, check_same_thread=False)
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS places_cache (
                    cache_key TEXT PRIMARY KEY,
                    cache_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _read_cache(self, cache_key: str) -> Optional[str]:
        cursor = self._conn.cursor()
        cursor.execute("SELECT payload FROM places_cache WHERE cache_key = ?", (cache_key,))
        row = cursor.fetchone()
        return str(row[0]) if row else None

    def _write_cache(self, cache_key: str, cache_type: str, payload: str) -> None:
        sql = (
            "INSERT OR REPLACE INTO places_cache "
            "(cache_key, cache_type, payload) VALUES (?, ?, ?)"
        )
        with self._conn:
            self._conn.execute(sql, (cache_key, cache_type, payload))

    def clear_cache(self) -> None:
        """Limpa todo o conteúdo do cache persistido."""
        with self._conn:
            self._conn.execute("DELETE FROM places_cache")

    def get_curated_lists(self, city_name: str) -> List[CurationList]:
        """Recupera listas de curadoria do cache SQLite ou, em miss, do adaptador de fallback."""
        cache_key = f"curated:{city_name.strip().lower()}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            raw_list = json.loads(cached)
            return [CurationList.model_validate(item) for item in raw_list]

        lists = self.fallback_adapter.get_curated_lists(city_name)
        serialized = json.dumps([cl.model_dump(mode="json") for cl in lists])
        self._write_cache(cache_key, "curated", serialized)
        return lists

    def search_places(
        self, query: str, city_name: Optional[str] = None
    ) -> List[POI]:
        """Pesquisa Pontos de Interesse no cache SQLite, com miss na API externa ou no fallback."""
        query_norm = query.strip().lower()
        if not query_norm:
            return []

        city_part = city_name.strip().lower() if city_name else ""
        cache_key = f"search:{query_norm}:{city_part}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            raw_list = json.loads(cached)
            return [POI.model_validate(item) for item in raw_list]

        results = self._fetch_places_on_miss(query, city_name)
        serialized = json.dumps([poi.model_dump(mode="json") for poi in results])
        self._write_cache(cache_key, "search", serialized)
        return results

    def _fetch_places_on_miss(
        self, query: str, city_name: Optional[str] = None
    ) -> List[POI]:
        if self.api_key:
            external_results = self._fetch_external_places(query, city_name)
            if external_results:
                return external_results
        return self.fallback_adapter.search_places(query, city_name)

    def _fetch_external_places(
        self, query: str, city_name: Optional[str] = None
    ) -> List[POI]:
        try:
            import httpx

            search_text = f"{query} {city_name}".strip() if city_name else query
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {"query": search_text, "key": self.api_key}
            resp = httpx.get(url, params=params, timeout=5.0)
            resp.raise_for_status()
            return self._parse_google_places_response(resp.json())
        except Exception:
            return []

    def _parse_google_places_response(self, data: dict[str, Any]) -> List[POI]:
        results: List[POI] = []
        for item in data.get("results", [])[:5]:
            loc = item.get("geometry", {}).get("location", {})
            types = item.get("types", [])
            poi = POI(
                id=item.get("place_id", f"ext-{item.get('name', 'poi')}"),
                name=item.get("name", "Unknown Place"),
                location=Coordinates(
                    latitude=float(loc.get("lat", 0.0)),
                    longitude=float(loc.get("lng", 0.0)),
                ),
                category=types[0] if types else "attraction",
                rating=float(item["rating"]) if "rating" in item else None,
                price_tier="$" * int(item.get("price_level", 2)),
            )
            results.append(poi)
        return results
