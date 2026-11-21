from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import Enum, StrEnum
from typing import Optional, Self

from pydantic import BaseModel, Field, model_validator, model_serializer


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

    @model_validator(mode="before")
    @classmethod
    def _accept_tuple(cls, data: object) -> object:
        if isinstance(data, (tuple, list)) and len(data) == 2:
            return {"latitude": data[0], "longitude": data[1]}
        return data

    def __iter__(self):
        return iter((self.latitude, self.longitude))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (tuple, list)) and len(other) == 2:
            return (self.latitude, self.longitude) == (other[0], other[1])
        return super().__eq__(other)

    @model_serializer
    def _serialize_tuple(self) -> tuple[float, float]:
        return (self.latitude, self.longitude)


class TimeWindow(BaseModel):
    start_time: time = Field(default=time(9, 0))
    end_time: time = Field(default=time(18, 0))

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_names(cls, data: object) -> object:
        if isinstance(data, dict):
            if "start" in data and "start_time" not in data:
                data = {**data, "start_time": data["start"]}
            if "end" in data and "end_time" not in data:
                data = {**data, "end_time": data["end"]}
        return data

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

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_names(cls, data: object) -> object:
        if isinstance(data, dict):
            if "coordinates" in data and "location" not in data:
                data = {**data, "location": data["coordinates"]}
            if "operating_window" in data and "window" not in data:
                data = {**data, "window": data["operating_window"]}
        return data

    @property
    def coordinates(self) -> Coordinates:
        return self.location

    @property
    def operating_window(self) -> TimeWindow:
        return self.window


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


class RouteStop(BaseModel):
    poi: POI
    start: datetime
    duration_minutes: int = Field(default=0, ge=0)

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.duration_minutes)


class Itinerary(BaseModel):
    stops: list[RouteStop | ItineraryStop] = Field(default_factory=list)
    total_utility: float = 0.0
    total_duration_minutes: int = 0


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
    id: str = ""
    from_stage_id: str = ""
    to_stage_id: str = ""
    mode: TransportMode = TransportMode.FLYING
    departure_time: date | datetime | None = None
    origin: str = ""
    destination: str = ""
    departure_datetime: datetime | None = None
    modal: str = "driving"
    boarding_cutoff_minutes: int | None = None

    @model_validator(mode="after")
    def _validate_legacy_contract(self) -> "InterCityConnection":
        if self.origin or self.destination:
            if not self.origin or not self.destination:
                raise ValueError("origin e destination são obrigatórios.")
            if self.departure_datetime is None:
                raise ValueError("departure_datetime é obrigatório.")
            if self.boarding_cutoff_minutes is None:
                cutoff = {"flying": 120, "driving": 30, "transit": 30}
                self.boarding_cutoff_minutes = cutoff.get(self.modal, 30)
        return self


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
