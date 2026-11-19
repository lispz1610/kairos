from __future__ import annotations

from datetime import date, time, timedelta
from enum import Enum, StrEnum
from typing import Optional, Self

from pydantic import BaseModel, Field, model_validator


class PriceTier(StrEnum):
    """Faixas de preço usadas na Estimativa de Gastos de Hospedagens e Pontos de Interesse."""

    BUDGET = "$"
    MODERATE = "$$"
    COMFORT = "$$$"
    LUXURY = "$$$$"


class FoodProfile(StrEnum):
    """Perfis de gasto diário com alimentação aplicados à Estimativa de Gastos da Viagem."""

    BUDGET = "budget"
    MODERATE = "moderate"
    FINE_DINING = "fine_dining"


class Coordinates(BaseModel):
    """Coordenada geográfica de um Ponto de Interesse ou de uma Hospedagem."""

    latitude: float
    longitude: float


class TimeWindow(BaseModel):
    """Janela de Disponibilidade ou Janela de Funcionamento com horários de início e fim."""

    start_time: time
    end_time: time

    @property
    def duration_minutes(self) -> int:
        """Calcular a duração da janela em minutos, limitada a zero quando invertida."""
        start_min = self.start_time.hour * 60 + self.start_time.minute
        end_min = self.end_time.hour * 60 + self.end_time.minute
        return max(0, end_min - start_min)

    def contains(self, t: time) -> bool:
        """Informar se o horário informado está dentro da janela, inclusive nas bordas."""
        return self.start_time <= t <= self.end_time


class TransportMode(str, Enum):
    """Modais de Transporte urbanos e interurbanos usados em Deslocamentos e Conexões."""

    WALKING = "walking"
    DRIVING = "driving"
    FLYING = "flying"
    TRANSIT = "transit"


class Accommodation(BaseModel):
    """Hospedagem que serve como Ponto de Partida/Retorno dos Roteiros de um Dia de Viagem."""

    id: str
    name: str
    location: Coordinates
    price_tier: PriceTier = PriceTier.MODERATE
    real_daily_rate: Optional[float] = None


class POI(BaseModel):
    """Ponto de Interesse com Janela de Funcionamento, permanência e Pontuação de Utilidade."""

    id: str
    name: str
    location: Coordinates
    window: TimeWindow = Field(
        default_factory=lambda: TimeWindow(start_time=time(9, 0), end_time=time(18, 0))
    )
    stay_duration_minutes: int = 60
    utility_score: float = 1.0
    category: str = "attraction"
    rating: Optional[float] = None
    price_tier: Optional[PriceTier] = None
    awards: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class MealSlot(BaseModel):
    """Slot de Refeição do Roteiro com janela, estabelecimentos recomendados e custo estimado."""

    id: str
    name: str
    window: TimeWindow
    recommended_places: list[POI] = Field(default_factory=list)
    selected_place: Optional[POI] = None
    estimated_cost: Optional[float] = None


class ItineraryStop(BaseModel):
    """Parada de um Roteiro com chegada, partida e Deslocamento até o Ponto de Interesse."""

    poi: POI
    arrival_time: time
    departure_time: time
    transit_duration_minutes: int = 0


class Itinerary(BaseModel):
    """Roteiro ordenado de paradas com Pontuação de Utilidade e duração totais acumuladas."""

    stops: list[ItineraryStop] = Field(default_factory=list)
    total_utility: float = 0.0
    total_duration_minutes: int = 0


class TripDay(BaseModel):
    """Dia de Viagem com Hospedagem, Janela de Disponibilidade, Slots de Refeição e Roteiro."""

    date: date
    base_accommodation: Accommodation
    custom_accommodation: Optional[Accommodation] = None
    previous_day_accommodation: Optional[Accommodation] = None
    include_luggage_dropoff: bool = False
    availability_window: TimeWindow = Field(
        default_factory=lambda: TimeWindow(start_time=time(9, 0), end_time=time(21, 0))
    )
    meal_slots: list[MealSlot] = Field(default_factory=list)
    itinerary: Optional[Itinerary] = None

    @property
    def effective_accommodation(self) -> Accommodation:
        """Obter a Hospedagem personalizada do dia ou, na ausência dela, a Hospedagem base."""
        return self.custom_accommodation or self.base_accommodation

    @property
    def departure_accommodation(self) -> Accommodation:
        """Obter a Hospedagem de partida, considerando o dia anterior em uma troca de Hospedagem."""
        return self.previous_day_accommodation or self.effective_accommodation

    @property
    def return_accommodation(self) -> Accommodation:
        """Obter a Hospedagem de retorno do Roteiro ao final do Dia de Viagem."""
        return self.effective_accommodation

    @property
    def is_transition_day(self) -> bool:
        """Informar se o Dia de Viagem troca de Hospedagem em relação ao dia anterior."""
        if self.previous_day_accommodation is None:
            return False
        return self.previous_day_accommodation.id != self.effective_accommodation.id


class TripStage(BaseModel):
    """Etapa de Viagem delimitada por cidade e período, composta por Dias de Viagem."""

    id: str
    city_name: str
    start_date: date
    end_date: date
    base_accommodation: Accommodation
    days: list[TripDay] = Field(default_factory=list)

    @classmethod
    def create(
        cls,
        id: str,
        city_name: str,
        start_date: date,
        end_date: date,
        base_accommodation: Accommodation,
    ) -> TripStage:
        """Criar uma Etapa de Viagem com os Dias de Viagem gerados entre as datas informadas."""
        stage = cls(
            id=id,
            city_name=city_name,
            start_date=start_date,
            end_date=end_date,
            base_accommodation=base_accommodation,
            days=[],
        )
        stage._generate_days()
        return stage

    def _generate_days(self) -> None:
        num_days = max(1, (self.end_date - self.start_date).days)
        generated_days: list[TripDay] = []
        current_date = self.start_date

        for i in range(num_days):
            prev_acc = generated_days[i - 1].effective_accommodation if i > 0 else None
            generated_days.append(
                TripDay(
                    date=current_date,
                    base_accommodation=self.base_accommodation,
                    previous_day_accommodation=prev_acc,
                )
            )
            current_date += timedelta(days=1)

        self.days = generated_days

    def override_accommodation(
        self, day_index: int, accommodation: Optional[Accommodation]
    ) -> None:
        """Substituir a Hospedagem do Dia de Viagem indicado e religar as partidas.

        Índices fora do intervalo de dias são ignorados.
        """
        if 0 <= day_index < len(self.days):
            self.days[day_index].custom_accommodation = accommodation
            self._relink_accommodations()

    def _relink_accommodations(self) -> None:
        for i in range(len(self.days)):
            if i > 0:
                self.days[i].previous_day_accommodation = self.days[i - 1].effective_accommodation
            else:
                self.days[i].previous_day_accommodation = None

    @model_validator(mode="after")
    def _relink_on_init(self) -> Self:
        if self.days:
            self._relink_accommodations()
        return self


class InterCityConnection(BaseModel):
    """Conexão Interurbana entre Etapas de Viagem com Modal de Transporte e data de partida."""

    id: str
    from_stage_id: str
    to_stage_id: str
    mode: TransportMode = TransportMode.FLYING
    departure_time: date


class PreferencesProfile(BaseModel):
    """Perfil de Preferência com intensidades de 0 a 10 por categoria temática."""

    intensities: dict[str, float] = Field(default_factory=dict)

    def get_intensity(self, category: str) -> float:
        """Obter a intensidade configurada para a categoria, ou zero quando ausente."""
        return self.intensities.get(category, 0.0)

    def set_intensity(self, category: str, value: float) -> None:
        """Definir a intensidade da categoria, limitando o valor ao intervalo de 0 a 10."""
        self.intensities[category] = max(0.0, min(10.0, float(value)))


class CurationList(BaseModel):
    """Lista de Curadoria temática com Pontos de Interesse e indicação de atividade."""

    id: str
    title: str
    description: Optional[str] = None
    items: list[POI] = Field(default_factory=list)
    is_active: bool = True


class Trip(BaseModel):
    """Viagem composta por Etapas de Viagem, Conexões Interurbanas e Perfil de Preferência."""

    id: str
    title: str
    travelers: int = 1
    notes: Optional[str] = None
    stages: list[TripStage] = Field(default_factory=list)
    connections: list[InterCityConnection] = Field(default_factory=list)
    preferences: PreferencesProfile = Field(default_factory=PreferencesProfile)
    curation_lists: list[CurationList] = Field(default_factory=list)

    @model_validator(mode="after")
    def _relink_stages_on_init(self) -> Self:
        for stage in self.stages:
            stage._relink_accommodations()
        return self
