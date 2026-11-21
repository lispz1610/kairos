from hypothesis import given
from hypothesis import strategies as st

from src.core.domain.models import POI, Coordinates, PreferencesProfile
from src.core.services.preferences import PreferencesService


@given(
    base_utility=st.floats(min_value=1.0, max_value=50.0),
    weight_low=st.floats(min_value=0.0, max_value=4.9),
    weight_high=st.floats(min_value=5.0, max_value=10.0),
)
def test_preference_monotonicity_property(
    base_utility: float,
    weight_low: float,
    weight_high: float,
) -> None:
    service = PreferencesService()
    poi = POI(
        id="poi-test",
        name="Test",
        location=Coordinates(latitude=0.0, longitude=0.0),
        category="Coffee Lover",
        utility_score=base_utility,
    )

    profile_low = PreferencesProfile(intensities={"Coffee Lover": weight_low})
    profile_high = PreferencesProfile(intensities={"Coffee Lover": weight_high})

    weighted_low = service.apply_preference_weights([poi], profile_low)[0]
    weighted_high = service.apply_preference_weights([poi], profile_high)[0]

    # Monotonic property: Higher intensity strictly increases or maintains utility
    assert weighted_high.utility_score > weighted_low.utility_score
    assert weighted_low.utility_score >= base_utility
    assert weighted_high.utility_score <= base_utility * 2.0
