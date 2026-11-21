"""Testes de ScheduleService (#34 e ripple shift).

AC3: ScheduleService valida o Roteiro contra os Horários de Funcionamento e
dentro da Janela de Disponibilidade; violações são reportadas como desvios
descritivos (lista de strings).
"""

from datetime import date, datetime, time

from src.core.domain.models import (
    POI,
    Accommodation,
    Coordinates,
    InterCityConnection,
    Itinerary,
    RouteStop,
    TimeWindow,
    Trip,
    TripStage,
)
from src.core.services.schedule import ScheduleService


def make_poi(
    opening: time = time(9, 0), closing: time = time(12, 0), poi_id: str = "POI-01"
) -> POI:
    """Criar POI de teste com horário de funcionamento configurável."""
    return POI(
        id=poi_id,
        name=f"POI {poi_id}",
        coordinates=(-23.5, -46.6),
        operating_window=TimeWindow(start=opening, end=closing),
    )


def make_itinerary(poi: POI, start: datetime, duration_minutes: int) -> Itinerary:
    """Criar Roteiro de teste com uma única parada."""
    return Itinerary(
        stops=[RouteStop(poi=poi, start=start, duration_minutes=duration_minutes)]
    )


def test_visita_dentro_do_horario_de_funcionamento_e_da_janela_de_disponibilidade() -> None:
    """Verifica que visita em conformidade com as janelas não gera desvios."""
    poi = make_poi(opening=time(9, 0), closing=time(12, 0))
    availability = TimeWindow(start=time(9, 0), end=time(23, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 10, 0), 30)

    assert ScheduleService.validate_itinerary(itinerary, availability) == []


def test_visita_antes_do_horario_de_funcionamento_reporta_desvio() -> None:
    """Verifica que visita antes da abertura reporta desvio."""
    poi = make_poi(opening=time(9, 0), closing=time(12, 0))
    availability = TimeWindow(start=time(8, 0), end=time(23, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 8, 45), 30)

    deviations = ScheduleService.validate_itinerary(itinerary, availability)

    assert deviations
    assert any("funcionamento" in deviation for deviation in deviations)


def test_visita_apos_fechamento_do_horario_reporta_desvio() -> None:
    """Verifica que visita após o fechamento reporta desvio."""
    poi = make_poi(opening=time(9, 0), closing=time(12, 0))
    availability = TimeWindow(start=time(8, 0), end=time(23, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 11, 50), 30)

    deviations = ScheduleService.validate_itinerary(itinerary, availability)

    assert deviations
    assert any("fechamento" in deviation for deviation in deviations)


def test_visita_que_termina_apos_o_término_da_janela_de_disponibilidade_reporta_desvio() -> None:
    """Verifica que visita que excede o fim da janela de disponibilidade reporta desvio."""
    poi = make_poi(opening=time(9, 0), closing=time(17, 0))
    availability = TimeWindow(start=time(8, 0), end=time(12, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 11, 30), 45)

    deviations = ScheduleService.validate_itinerary(itinerary, availability)

    assert deviations
    assert any(
        "Disponibilidade" in deviation or "disponibilidade" in deviation
        for deviation in deviations
    )


def test_visita_que_comeca_antes_do_inicio_da_janela_de_disponibilidade_reporta_desvio() -> None:
    """Verifica que visita iniciada antes do início da janela de disponibilidade reporta desvio."""
    poi = make_poi(opening=time(9, 0), closing=time(17, 0))
    availability = TimeWindow(start=time(10, 0), end=time(23, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 9, 30), 30)

    deviations = ScheduleService.validate_itinerary(itinerary, availability)

    assert deviations
    assert any(
        "Disponibilidade" in deviation or "disponibilidade" in deviation
        for deviation in deviations
    )


def test_ripple_shift_extends_stage_and_shifts_subsequent_stages_and_connections() -> None:
    """Verifica o Deslocamento em Cascata sobre Etapas e Conexões Interurbanas."""
    hotel_sp = Accommodation(
        id="h-sp", name="Hotel SP", location=Coordinates(latitude=-23.5, longitude=-46.6)
    )
    hotel_lima = Accommodation(
        id="h-lima", name="Hotel Lima", location=Coordinates(latitude=-12.0, longitude=-77.0)
    )

    stage_sp = TripStage.create(
        id="stage-sp",
        city_name="São Paulo",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 10),
        base_accommodation=hotel_sp,
    )
    stage_lima = TripStage.create(
        id="stage-lima",
        city_name="Lima",
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 15),
        base_accommodation=hotel_lima,
    )
    flight = InterCityConnection(
        id="flight-1",
        from_stage_id="stage-sp",
        to_stage_id="stage-lima",
        departure_time=date(2026, 11, 10),
    )

    trip = Trip(
        id="trip-1",
        title="SP e Lima",
        stages=[stage_sp, stage_lima],
        connections=[flight],
    )

    service = ScheduleService()
    preview = service.preview_ripple_shift(trip, target_stage_id="stage-sp", delta_days=1)
    assert preview.delta_days == 1
    assert preview.new_target_end == date(2026, 11, 11)

    updated_trip = service.apply_ripple_shift(trip, target_stage_id="stage-sp", delta_days=1)

    assert len(updated_trip.stages[0].days) == 10
    assert updated_trip.stages[0].end_date == date(2026, 11, 11)
    assert updated_trip.stages[0].days[-1].date == date(2026, 11, 10)

    assert updated_trip.stages[1].start_date == date(2026, 11, 11)
    assert updated_trip.stages[1].end_date == date(2026, 11, 16)
    assert len(updated_trip.stages[1].days) == 5
    assert updated_trip.stages[1].days[0].date == date(2026, 11, 11)
    assert updated_trip.stages[1].days[-1].date == date(2026, 11, 15)

    assert updated_trip.connections[0].departure_time == date(2026, 11, 11)
