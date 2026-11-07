from datetime import date, time

from src.core.domain.models import (
    POI,
    Accommodation,
    Coordinates,
    InterCityConnection,
    Itinerary,
    ItineraryStop,
    MealSlot,
    TimeWindow,
    Trip,
    TripStage,
)
from src.core.services.markdown_export import MarkdownExportService


def test_markdown_export_service_structure() -> None:
    hotel_sp = Accommodation(
        id="h-sp",
        name="Hotel Fasano SP",
        location=Coordinates(latitude=-23.56, longitude=-46.66),
        price_tier="$$$$",
        real_daily_rate=1200.0,
    )
    hotel_boutique = Accommodation(
        id="h-boutique",
        name="Hotel Boutique Jardins",
        location=Coordinates(latitude=-23.57, longitude=-46.67),
        price_tier="$$$",
        real_daily_rate=800.0,
    )

    stage_sp = TripStage.create(
        id="st-sp",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 3),  # 2 days
        base_accommodation=hotel_sp,
    )
    # Day 2 has custom boutique hotel
    stage_sp.override_accommodation(day_index=1, accommodation=hotel_boutique)

    masp = POI(
        id="masp",
        name="Museu de Arte de São Paulo (MASP)",
        location=Coordinates(latitude=-23.56, longitude=-46.65),
        stay_duration_minutes=120,
        utility_score=9.5,
        awards=["Patrimônio Histórico"],
    )
    stage_sp.days[0].itinerary = Itinerary(
        stops=[
            ItineraryStop(
                poi=masp,
                arrival_time=time(10, 0),
                departure_time=time(12, 0),
                transit_duration_minutes=15,
            )
        ],
        total_utility=9.5,
        total_duration_minutes=150,
    )
    stage_sp.days[0].meal_slots = [
        MealSlot(
            id="slot-1",
            name="Almoço",
            window=TimeWindow(start_time=time(12, 30), end_time=time(14, 0)),
            selected_place=POI(
                id="rest-1",
                name="A Baianeira MASP",
                location=Coordinates(latitude=-23.56, longitude=-46.65),
                price_tier="$$",
                awards=["Bib Gourmand Michelin"],
            ),
            estimated_cost=95.0,
        )
    ]

    flight = InterCityConnection(
        id="fl-1",
        from_stage_id="st-sp",
        to_stage_id="st-lima",
        departure_time=date(2026, 11, 3),
    )

    trip = Trip(
        id="trip-1",
        title="Viagem Gastronômica & Cultural",
        stages=[stage_sp],
        connections=[flight],
    )

    service = MarkdownExportService()
    md_content = service.export_trip_markdown(trip)

    # Assertions on Markdown structure
    assert "# 🌍 Viagem Gastronômica & Cultural" in md_content
    assert "## 💰 Quadro Orçamentário Estimado" in md_content
    assert "## 📅 Caderno Diário Detalhado" in md_content
    assert "São Paulo" in md_content
    assert "Hotel Fasano SP" in md_content
    assert "Hotel Boutique Jardins" in md_content
    assert "MASP" in md_content
    assert "A Baianeira MASP" in md_content
    assert "Bib Gourmand Michelin" in md_content
    assert "Troca de Hospedagem" in md_content
