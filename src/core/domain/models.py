from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from enum import Enum, StrEnum
from typing import Any, Optional, Self

from pydantic import BaseModel, Field, field_serializer, model_validator


class PriceTier(StrEnum):
    BUDGET = "$"
    MODERATE = "$$"
    COMFORT = "$$$"
    LUXURY = "$$$$"


class FoodProfile(StrEnum):
    BUDGET = "budget"
    MODERATE = "moderate"
    FINE_DINING = "fine_dining"


class Coordinates(BaseModel):
    latitude: float
    longitude: float

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: Any, handler: Any) -> Any:
        return handler(
            core_schema.tuple_schema(
                [core_schema.float_schema(), core_schema.float_schema()]
            )
        )

    @model_validator(mode="before")
    @classmethod
    def _from_tuple(cls, data: Any) -> dict[str, float] | Any:
        if isinstance(data, (tuple, list)) and len(data) == 2:
            return {"latitude": data[0], "longitude": data[1]}
        return data

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Coordinates):
            return self.latitude == other.latitude and self.longitude == other.longitude
        if isinstance(other, tuple):
            return len(other) == 2 and self.latitude == other[0] and self.longitude == other[1]
        if isinstance(other, list):
            return len(other) == 2 and self.latitude == other[0] and self.longitude == other[1]
        return False

    def as_tuple(self) -> tuple[float, float]:
        """Return coordinates as (latitude, longitude) tuple."""
        return (self.latitude, self.longitude)

    @field_serializer("latitude", "longitude", when_used="json")
    def serialize_coords(self, value: float) -> float:
        return value


class TimeWindow(BaseModel):
    start_time: time = Field(alias="start")
    end_time: time = Field(alias="end")

    @property
    def start(self) -> time:
        return self.start_time

    @property
    def end(self) -> time:
        return self.end_time

    @property
    def duration_minutes(self) -> int:
        start_min = self.start_time.hour * 60 + self.start_time.minute
        end_min = self.end_time.hour * 60 + self.end_time.minute
        return max(0, end_min - start_min)

    def contains(self, t: time) -> bool:
        return self.start_time <= t <= self.end_time

    class Config:
        populate_by_name = True


class TransportMode(str, Enum):
    WALKING = "walking"
    DRIVING = "driving"
    FLYING = "flying"
    TRANSIT = "transit"


class Accommodation(BaseModel):
    id: str
    name: str
    location: Coordinates
    price_tier: PriceTier = PriceTier.MODERATE
    real_daily_rate: Optional[float] = None


class POI(BaseModel):
    id: str
    name: str
    location: Coordinates = Field(alias="coordinates")
    window: TimeWindow = Field(
        alias="operating_window",
        default_factory=lambda: TimeWindow(start_time=time(9, 0), end_time=time(18, 0))
    )
    stay_duration_minutes: int = 60
    utility_score: float = 1.0
    category: str = "attraction"
    rating: Optional[float] = None
    price_tier: Optional[PriceTier] = None
    awards: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @property
    def operating_window(self) -> TimeWindow:
        return self.window

    @property
    def coordinates(self) -> Coordinates:
        return self.location

    class Config:
        populate_by_name = True


class MealSlot(BaseModel):
    id: str
    name: str
    window: TimeWindow
    recommended_places: list[POI] = Field(default_factory=list)
    selected_place: Optional[POI] = None
    estimated_cost: Optional[float] = None


class ItineraryStop(BaseModel):
    poi: POI
    arrival_time: time
    departure_time: time
    transit_duration_minutes: int = 0

    @property
    def end(self) -> time:
        """Fim da visita ao POI."""
        return self.departure_time

    @property
    def start(self) -> time:
        """Início da visita ao POI."""
        return self.arrival_time


class RouteStop(BaseModel):
    """Visita a um Ponto de Interesse: ``poi``, ``start`` e Tempo de Permanência."""

    poi: POI = Field(description="Ponto de Interesse visitado.")
    start: datetime = Field(description="Horário de início da visita ao POI.")
    duration_minutes: int = Field(
        ge=0, description="Tempo de Permanência no POI, em minutos."
    )

    @property
    def end(self) -> datetime:
        """Terceiro do visitante: ``start`` + Tempo de Permanência no POI."""
        return self.start + timedelta(minutes=self.duration_minutes)


class Itinerary(BaseModel):
    stops: list[ItineraryStop | RouteStop] = Field(default_factory=list)
    total_utility: float = 0.0
    total_duration_minutes: int = 0
    start_location: Coordinates | None = Field(
        default=None,
        description=(
            "Coordenada do início do Roteiro replanejado — a coordenada atual "
            "do visitante."
        ),
    )


class TripDay(BaseModel):
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
        return self.custom_accommodation or self.base_accommodation

    @property
    def departure_accommodation(self) -> Accommodation:
        return self.previous_day_accommodation or self.effective_accommodation

    @property
    def return_accommodation(self) -> Accommodation:
        return self.effective_accommodation

    @property
    def is_transition_day(self) -> bool:
        if self.previous_day_accommodation is None:
            return False
        return self.previous_day_accommodation.id != self.effective_accommodation.id


class TripStage(BaseModel):
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
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_stage_id: str = ""
    to_stage_id: str = ""
    mode: TransportMode = TransportMode.FLYING
    departure_time: date | None = None
    departure_datetime: datetime = Field(description="Partida com data e hora.")
    modal: str = Field(
        default="driving",
        min_length=1,
        description="Modal de Transporte da Conexão Interurbana.",
    )
    boarding_cutoff_minutes: int = Field(
        ge=0,
        default=30,
        description=(
            "Margem de Embarque em minutos; o padrão do Modal de Transporte é "
            "aplicado quando não informado."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _apply_modal_default(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "departure_datetime" not in data or data["departure_datetime"] is None:
                dep_time = data.get("departure_time")
                if dep_time is not None:
                    if isinstance(dep_time, datetime):
                        data = {**data, "departure_datetime": dep_time}
                    elif isinstance(dep_time, date):
                        combined = datetime.combine(dep_time, time(0, 0))
                        data = {**data, "departure_datetime": combined}
                    elif isinstance(dep_time, str):
                        try:
                            parsed = datetime.fromisoformat(dep_time)
                        except ValueError:
                            parsed = datetime.combine(
                                date.fromisoformat(dep_time), time(0, 0)
                            )
                        data = {**data, "departure_datetime": parsed}
            if data.get("boarding_cutoff_minutes") is None:
                modal = data.get("modal") or "driving"
                data = {
                    **data,
                    "boarding_cutoff_minutes": {"flying": 120, "driving": 30, "transit": 30}.get(
                        modal, 30
                    ),
                }
        return data

    @model_validator(mode="after")
    def _set_departure_time_from_datetime(self) -> Self:
        """Define departure_time a partir de departure_datetime se não informado."""
        if self.departure_time is None and self.departure_datetime is not None:
            self.departure_time = self.departure_datetime.date()
        return self

    @property
    def effective_departure_time(self) -> date:
        """Data de partida efetiva: usa departure_time ou calcula a partir de departure_datetime."""
        if self.departure_time is not None:
            return self.departure_time
        return self.departure_datetime.date()


class PreferencesProfile(BaseModel):
    intensities: dict[str, float] = Field(default_factory=dict)

    def get_intensity(self, category: str) -> float:
        return self.intensities.get(category, 0.0)

    def set_intensity(self, category: str, value: float) -> None:
        self.intensities[category] = max(0.0, min(10.0, float(value)))


class CurationList(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    items: list[POI] = Field(default_factory=list)
    is_active: bool = True


class Trip(BaseModel):
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
