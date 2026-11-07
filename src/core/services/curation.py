from __future__ import annotations

from typing import Dict, List, Optional

from src.core.domain.models import POI, Coordinates, CurationList, TimeWindow

# Catálogo estático curado para modo Offline Replay (São Paulo e Lima) — ADR 0005
MOCK_CURATED_CATALOG: Dict[str, List[CurationList]] = {
    "São Paulo": [
        CurationList(
            id="sp-michelin",
            title="Guia Michelin (Estrelas & Bib Gourmand)",
            description="Seleção oficial do Guia Michelin em São Paulo.",
            items=[
                POI(
                    id="sp-dom",
                    name="D.O.M. (Alex Atala)",
                    location=Coordinates(latitude=-23.5658, longitude=-46.6672),
                    category="restaurant",
                    rating=4.7,
                    price_tier="$$$$",
                    awards=["Michelin 2 Estrelas"],
                    utility_score=10.0,
                ),
                POI(
                    id="sp-mani",
                    name="Maní (Helena Rizzo)",
                    location=Coordinates(latitude=-23.5684, longitude=-46.6853),
                    category="restaurant",
                    rating=4.6,
                    price_tier="$$$$",
                    awards=["Michelin 1 Estrela"],
                    utility_score=9.5,
                ),
                POI(
                    id="sp-baianeira",
                    name="A Baianeira MASP",
                    location=Coordinates(latitude=-23.5615, longitude=-46.6559),
                    category="restaurant",
                    rating=4.8,
                    price_tier="$$",
                    awards=["Bib Gourmand Michelin"],
                    utility_score=9.0,
                ),
            ],
        ),
        CurationList(
            id="sp-coffee",
            title="Cafeterias Especiais & Specialty Coffee",
            description="Os melhores grãos e métodos artesanais da capital paulista.",
            items=[
                POI(
                    id="sp-coffeelab",
                    name="Coffee Lab (Vila Madalena)",
                    location=Coordinates(latitude=-23.5552, longitude=-46.6908),
                    category="Coffee Lover",
                    rating=4.8,
                    price_tier="$$",
                    awards=["Melhor Cafeteria SP"],
                    utility_score=9.5,
                ),
                POI(
                    id="sp-dolares",
                    name="Por um Punhado de Dólares (República)",
                    location=Coordinates(latitude=-23.5492, longitude=-46.6475),
                    category="Coffee Lover",
                    rating=4.6,
                    price_tier="$",
                    utility_score=8.5,
                ),
            ],
        ),
        CurationList(
            id="sp-bakeries",
            title="Padarias & Docerias Artesanais",
            description="Pães de fermentação natural e confeitarias de destaque.",
            items=[
                POI(
                    id="sp-fabrique",
                    name="Fabrique Pão e Café",
                    location=Coordinates(latitude=-23.5358, longitude=-46.6575),
                    category="bakery",
                    rating=4.7,
                    price_tier="$$",
                    utility_score=8.8,
                )
            ],
        ),
    ],
    "Lima": [
        CurationList(
            id="lima-50best",
            title="Latin America's 50 Best Restaurants",
            description="Ícones da alta gastronomia peruana em Lima.",
            items=[
                POI(
                    id="lima-central",
                    name="Central (Virgilio Martínez)",
                    location=Coordinates(latitude=-12.1528, longitude=-77.0227),
                    category="restaurant",
                    rating=4.9,
                    price_tier="$$$$",
                    awards=["The World's Best 2023", "50 Best"],
                    utility_score=10.0,
                ),
                POI(
                    id="lima-maido",
                    name="Maido (Mitsuharu Tsumura)",
                    location=Coordinates(latitude=-12.1264, longitude=-77.0298),
                    category="restaurant",
                    rating=4.8,
                    price_tier="$$$$",
                    awards=["50 Best Nikkei"],
                    utility_score=9.8,
                ),
            ],
        ),
        CurationList(
            id="lima-coffee",
            title="Especialidades de Café em Miraflores & Barranco",
            description="Cafés de origem única cultivados nos Andes e na Amazônia peruana.",
            items=[
                POI(
                    id="lima-origen",
                    name="Origen Tostadores de Café",
                    location=Coordinates(latitude=-12.1120, longitude=-77.0380),
                    category="Coffee Lover",
                    rating=4.7,
                    price_tier="$$",
                    awards=["Campeão Barista Peru"],
                    utility_score=9.0,
                )
            ],
        ),
    ],
}


class CurationService:
    """Gerencia listas de curadoria pública e listas personalizadas do usuário."""

    def get_suggested_curation_lists(self, city_name: str) -> List[CurationList]:
        return MOCK_CURATED_CATALOG.get(city_name, [])

    def apply_curation_boost(
        self,
        candidates: List[POI],
        active_curation_lists: List[CurationList],
        boost_multiplier: float = 1.5,
    ) -> List[POI]:
        if not active_curation_lists:
            return candidates

        # Conjunto de IDs e nomes curados
        curated_ids = {
            item.id for cl in active_curation_lists for item in cl.items
        }
        curated_names = {
            item.name.lower() for cl in active_curation_lists for item in cl.items
        }

        boosted_list: List[POI] = []
        for poi in candidates:
            is_curated = (
                poi.id in curated_ids or poi.name.lower() in curated_names
            )
            if is_curated:
                boosted_poi = poi.model_copy(
                    update={"utility_score": poi.utility_score * boost_multiplier}
                )
                boosted_list.append(boosted_poi)
            else:
                boosted_list.append(poi)

        return boosted_list

    def search_places_autocomplete(
        self, query: str, city_name: Optional[str] = None
    ) -> List[POI]:
        query_norm = query.lower()
        results: List[POI] = []

        # Pesquisa no catálogo mock offline de POIs
        for city, lists in MOCK_CURATED_CATALOG.items():
            if city_name and city.lower() != city_name.lower():
                continue
            for cl in lists:
                for item in cl.items:
                    if query_norm in item.name.lower() or query_norm in item.category.lower():
                        results.append(item)

        # Fallback genérico caso nada seja encontrado
        if not results:
            from datetime import time
            results.append(
                POI(
                    id=f"custom-place-{abs(hash(query))}",
                    name=query,
                    location=Coordinates(latitude=-23.55, longitude=-46.63),
                    window=TimeWindow(start_time=time(9, 0), end_time=time(20, 0)),
                    category="custom",
                    utility_score=7.0,
                )
            )

        return results[:5]
