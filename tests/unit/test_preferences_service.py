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
