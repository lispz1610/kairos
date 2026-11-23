from datetime import date, time

import pytest

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


@pytest.mark.requirement("RF02")
def test_markdown_export_service_structure() -> None:
    """Verifica a estrutura completa do Markdown exportado de uma Viagem."""
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
    # Day 2 has custom boutique hotel and luggage dropoff
    stage_sp.override_accommodation(day_index=1, accommodation=hotel_boutique)
    stage_sp.days[1].include_luggage_dropoff = True

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

    # 1. Cabeçalho e Metadados Globais
    assert "# 🌍 Viagem Gastronômica & Cultural" in md_content
    assert "Guia estruturado de viagem" in md_content
    assert "👥 **Viajantes**: 1 pessoa(s)" in md_content

    # 2. Quadro Orçamentário Consolidado
    assert "## 💰 Quadro Orçamentário Estimado" in md_content
    assert "| `st-sp` | 2 |" in md_content

    # 3. Caderno Diário e Etapas
    assert "## 📅 Caderno Diário Detalhado" in md_content
    assert "São Paulo" in md_content

    # 4. Hospedagens e Dia de Troca de Hospedagem
    assert "Hotel Fasano SP" in md_content
    assert "Hotel Boutique Jardins" in md_content
    assert "Dia de Troca de Hospedagem" in md_content
    assert "Check-in e Parada de Malas" in md_content

    # 5. Roteiro de Visitas e Pontos de Interesse
    assert "MASP" in md_content
    assert "Patrimônio Histórico" in md_content

    # 6. Slots de Refeição e Gastronomia Curada
    assert "A Baianeira MASP" in md_content
    assert "Bib Gourmand Michelin" in md_content


@pytest.mark.requirement("RF02")
def test_markdown_export_relinks_deserialized_trip_accommodations() -> None:
    """Verifica que a exportação reconhece dias de troca após desserialização."""
    import json

    base_hotel = Accommodation(
        id="h-base",
        name="Hotel Base",
        location=Coordinates(latitude=-23.55, longitude=-46.66),
    )
    custom_hotel = Accommodation(
        id="h-custom",
        name="Hotel Custom",
        location=Coordinates(latitude=-23.56, longitude=-46.67),
    )
    stage = TripStage.create(
        id="st-test",
        city_name="Curitiba",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 4),
        base_accommodation=base_hotel,
    )
    stage.override_accommodation(day_index=1, accommodation=custom_hotel)
    stage.days[1].include_luggage_dropoff = True

    trip = Trip(id="trip-deser", title="Viagem Deserializada", stages=[stage])

    # Simulate deserialization from JSON where previous_day_accommodation was omitted/null
    data = json.loads(trip.model_dump_json())
    for s in data["stages"]:
        for d in s["days"]:
            d["previous_day_accommodation"] = None

    restored_trip = Trip.model_validate(data)
    service = MarkdownExportService()
    md = service.export_trip_markdown(restored_trip)

    # Verificação de re-vinculação de hospedagens e dia de transição
    assert "Dia de Troca de Hospedagem" in md
    assert "Check-in e Parada de Malas" in md
    assert "Hotel Custom" in md
