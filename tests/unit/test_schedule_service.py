"""Testes unitários de ``ScheduleService`` (#34).

``ScheduleService.validate_itinerary`` cobre o contrato de #34: cada visita
planejada no Roteiro deve estar dentro do horário de funcionamento do POI e
dentro da Janela de Disponibilidade; violações são reportadas como desvios
descritivos (lista de strings).
"""

from datetime import datetime, time

from src.core.domain.models import Itinerary, POI, RouteStop, TimeWindow
from src.core.services.schedule import ScheduleService


def make_poi(opening=time(9, 0), closing=time(12, 0), poi_id="POI-01"):
    return POI(
        id=poi_id,
        name=f"POI {poi_id}",
        coordinates=(-23.5, -46.6),
        operating_window=TimeWindow(start=opening, end=closing),
    )


def make_itinerary(poi, start, duration_minutes):
    return Itinerary(
        stops=[RouteStop(poi=poi, start=start, duration_minutes=duration_minutes)]
    )


def test_visita_dentro_do_horario_de_funcionamento_e_da_janela_de_disponibilidade():
    poi = make_poi(opening=time(9, 0), closing=time(12, 0))
    availability = TimeWindow(start=time(9, 0), end=time(23, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 10, 0), 30)

    assert ScheduleService.validate_itinerary(itinerary, availability) == []


def test_visita_antes_do_horario_de_funcionamento_reporta_desvio():
    poi = make_poi(opening=time(9, 0), closing=time(12, 0))
    availability = TimeWindow(start=time(8, 0), end=time(23, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 8, 45), 30)

    deviations = ScheduleService.validate_itinerary(itinerary, availability)

    assert deviations
    assert any("funcionamento" in deviation for deviation in deviations)


def test_visita_apos_fechamento_do_horario_reporta_desvio():
    poi = make_poi(opening=time(9, 0), closing=time(12, 0))
    availability = TimeWindow(start=time(8, 0), end=time(23, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 11, 50), 30)

    deviations = ScheduleService.validate_itinerary(itinerary, availability)

    assert deviations
    assert any("fechamento" in deviation for deviation in deviations)


def test_visita_que_termina_apos_o_término_da_janela_de_disponibilidade_reporta_desvio():
    poi = make_poi(opening=time(9, 0), closing=time(17, 0))
    availability = TimeWindow(start=time(8, 0), end=time(12, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 11, 30), 45)

    deviations = ScheduleService.validate_itinerary(itinerary, availability)

    assert deviations
    assert any(
        "Disponibilidade" in deviation or "disponibilidade" in deviation
        for deviation in deviations
    )


def test_visita_que_comeca_antes_do_inicio_da_janela_de_disponibilidade_reporta_desvio():
    poi = make_poi(opening=time(9, 0), closing=time(17, 0))
    availability = TimeWindow(start=time(10, 0), end=time(23, 0))
    itinerary = make_itinerary(poi, datetime(2026, 11, 20, 9, 30), 30)

    deviations = ScheduleService.validate_itinerary(itinerary, availability)

    assert deviations
    assert any(
        "Disponibilidade" in deviation or "disponibilidade" in deviation
        for deviation in deviations
    )
