import pytest

from src.core.domain.models import POI, Coordinates, PreferencesProfile
from src.core.services.preferences import PreferencesService


def test_preference_intensity_modulates_utility() -> None:
    service = PreferencesService()
    profile = PreferencesProfile(
        intensities={"Museum Lover": 10.0, "Nature Lover": 0.0}
    )

    museum = POI(
        id="p1",
        name="Museu",
        location=Coordinates(latitude=0.0, longitude=0.0),
        category="Museum Lover",
        utility_score=10.0,
    )
    park = POI(
        id="p2",
        name="Parque",
        location=Coordinates(latitude=0.0, longitude=0.0),
        category="Nature Lover",
        utility_score=10.0,
    )

    weighted = service.apply_preference_weights([museum, park], profile)
    w_museum = next(p for p in weighted if p.id == "p1")
    w_park = next(p for p in weighted if p.id == "p2")

    # 10.0 * (1 + 10/10) = 20.0
    assert w_museum.utility_score == 20.0
    # 10.0 * (1 + 0/10) = 10.0
    assert w_park.utility_score == 10.0


def test_thematic_slots_generation_for_coffee_and_wine_lovers() -> None:
    service = PreferencesService()
    profile = PreferencesProfile(
        intensities={"Coffee Lover": 8.0, "Wine Lover": 6.0}
    )
    ref_loc = Coordinates(latitude=-23.56, longitude=-46.66)

    cafe = POI(
        id="c1",
        name="Coffee Lab",
        location=Coordinates(latitude=-23.561, longitude=-46.661),
        category="Coffee Lover",
    )
    wine_bar = POI(
        id="w1",
        name="Bardega Wine Bar",
        location=Coordinates(latitude=-23.562, longitude=-46.662),
        category="Wine Lover",
    )

    slots = service.generate_thematic_slots(
        profile=profile,
        reference_location=ref_loc,
        cafe_candidates=[cafe],
        wine_candidates=[wine_bar],
    )

    slot_names = [s.name for s in slots]
    assert "Pausa para Café" in slot_names
    assert "Degustação / Wine Bar" in slot_names
    assert len(slots) == 2


def test_all_six_preference_categories_modulate_utility() -> None:
    service = PreferencesService()
    profile = PreferencesProfile(
        intensities={
            "Coffee Lover": 10.0,
            "Wine Lover": 8.0,
            "Museum Lover": 6.0,
            "Nature Lover": 4.0,
            "Gastronomy & Fine Dining": 5.0,
            "Street Food": 2.0,
        }
    )

    pois = [
        POI(
            id="poi-coffee",
            name="Cafeteria Especial",
            location=Coordinates(latitude=0.0, longitude=0.0),
            category="cafe",
            utility_score=10.0,
        ),
        POI(
            id="poi-wine",
            name="Wine Bar Boutique",
            location=Coordinates(latitude=0.0, longitude=0.0),
            category="wine_bar",
            utility_score=10.0,
        ),
        POI(
            id="poi-museum",
            name="Galeria de Arte",
            location=Coordinates(latitude=0.0, longitude=0.0),
            category="museum",
            utility_score=10.0,
        ),
        POI(
            id="poi-nature",
            name="Parque Ibirapuera",
            location=Coordinates(latitude=0.0, longitude=0.0),
            category="park",
            utility_score=10.0,
        ),
        POI(
            id="poi-gastro",
            name="Restaurante Autoral",
            location=Coordinates(latitude=0.0, longitude=0.0),
            category="restaurant",
            utility_score=10.0,
        ),
        POI(
            id="poi-street",
            name="Mercado de Rua",
            location=Coordinates(latitude=0.0, longitude=0.0),
            category="street_food",
            utility_score=10.0,
        ),
    ]

    weighted = service.apply_preference_weights(pois, profile)
    weighted_by_id = {p.id: p.utility_score for p in weighted}

    # Base = 10.0. Multiplier = 1.0 + (intensity / 10.0)
    assert weighted_by_id["poi-coffee"] == pytest.approx(20.0)  # 10.0 * 2.0
    assert weighted_by_id["poi-wine"] == pytest.approx(18.0)  # 10.0 * 1.8
    assert weighted_by_id["poi-museum"] == pytest.approx(16.0)  # 10.0 * 1.6
    assert weighted_by_id["poi-nature"] == pytest.approx(14.0)  # 10.0 * 1.4
    assert weighted_by_id["poi-gastro"] == pytest.approx(15.0)  # 10.0 * 1.5
    assert weighted_by_id["poi-street"] == pytest.approx(12.0)  # 10.0 * 1.2
