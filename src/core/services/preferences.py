from __future__ import annotations

from typing import Dict, Set

from src.core.domain.models import POI, PreferencesProfile

CATEGORY_SYNONYMS: Dict[str, Set[str]] = {
    "Coffee Lover": {"coffee lover", "cafe", "coffee", "cafeteria"},
    "Wine Lover": {"wine lover", "wine_bar", "wine", "winery", "enoteca"},
    "Museum Lover": {"museum lover", "museum", "museu", "art_gallery", "gallery"},
    "Nature Lover": {"nature lover", "park", "parque", "garden", "nature"},
    "Gastronomy & Fine Dining": {
        "gastronomy & fine dining",
        "restaurant",
        "restaurante",
        "fine_dining",
    },
    "Street Food": {"street food", "street_food", "snack", "market"},
}


class PreferencesService:
    """Modula a atratividade de POIs por intensidades (0 a 10) do Perfil de Preferência."""

    def apply_preference_weights(
        self, candidates: list[POI], profile: PreferencesProfile
    ) -> list[POI]:
        """Aplicar o Perfil de Preferência à Pontuação de Utilidade dos candidatos."""
        weighted_list: list[POI] = []
        for poi in candidates:
            intensity = self._match_intensity(poi, profile)
            multiplier = 1.0 + (intensity / 10.0)
            weighted_poi = poi.model_copy(
                update={"utility_score": poi.utility_score * multiplier}
            )
            weighted_list.append(weighted_poi)
        return weighted_list

    def _match_intensity(self, poi: POI, profile: PreferencesProfile) -> float:
        poi_cat = poi.category.lower()
        poi_tags = {poi_cat} | {a.lower() for a in poi.awards}

        max_intensity = profile.get_intensity(poi.category)
        for tag, intensity in profile.intensities.items():
            synonyms = CATEGORY_SYNONYMS.get(tag, {tag.lower()})
            if any(syn in poi_tags or poi_cat in syn for syn in synonyms):
                max_intensity = max(max_intensity, intensity)

        return max_intensity
