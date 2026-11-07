from __future__ import annotations

from datetime import date, time, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class TimeWindow(BaseModel):
    start_time: time
    end_time: time

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
    price_tier: str = "$$"
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
    price_tier: Optional[str] = None
    awards: list[str] = Field(default_factory=list)


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


class Itinerary(BaseModel):
    stops: list[ItineraryStop] = Field(default_factory=list)
    total_utility: float = 0.0
    total_duration_minutes: int = 0


class TripDay(BaseModel):
    date: date
    base_accommodation: Accommodation
    custom_accommodation: Optional[Accommodation] = None
    previous_day_accommodation: Optional[Accommodation] = None
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


class InterCityConnection(BaseModel):
    id: str
    from_stage_id: str
    to_stage_id: str
    mode: TransportMode = TransportMode.FLYING
    departure_time: date


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


class Trip(BaseModel):
    id: str
    title: str
    stages: list[TripStage] = Field(default_factory=list)
    connections: list[InterCityConnection] = Field(default_factory=list)
    preferences: PreferencesProfile = Field(default_factory=PreferencesProfile)
    curation_lists: list[CurationList] = Field(default_factory=list)
