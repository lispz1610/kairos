from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from enum import Enum, StrEnum
from types import UnionType
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Optional,
    Self,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    SerializerFunctionWrapHandler,
    field_serializer,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_core import core_schema

_TParsed = TypeVar("_TParsed")


def _parse_iso(parser: Callable[[str], _TParsed]) -> Callable[[Any], Any]:
    """Aceitar valores ISO em texto mesmo quando a validação está em modo estrito."""

    def convert(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return parser(value)
            except ValueError:
                return value
        return value

    return convert


_TEnum = TypeVar("_TEnum", bound=Enum)


def _parse_enum(enum_type: type[_TEnum]) -> Callable[[Any], Any]:
    """Criar um conversor que aceita o valor textual de uma enumeração conhecida."""

    def convert(value: Any) -> Any:
        if isinstance(value, str) and not isinstance(value, enum_type):
            try:
                return enum_type(value)
            except ValueError:
                return value
        return value

    return convert


IsoDate = Annotated[date, BeforeValidator(_parse_iso(date.fromisoformat))]
IsoDatetime = Annotated[datetime, BeforeValidator(_parse_iso(datetime.fromisoformat))]
IsoTime = Annotated[time, BeforeValidator(_parse_iso(time.fromisoformat))]


def _field_input_names(field: FieldInfo) -> set[str]:
    """Coletar o nome canônico e os aliases aceitos na entrada de um campo."""
    names: set[str] = set()
    alias = field.validation_alias if field.validation_alias is not None else field.alias
    if isinstance(alias, AliasChoices):
        names.update(str(choice) for choice in alias.choices if isinstance(choice, str))
    elif isinstance(alias, str):
        names.add(alias)
    return names


def _allowed_input_names(model: type[BaseModel]) -> set[str]:
    """Coletar nomes canônicos e aliases aceitos na entrada de um modelo."""
    names = set(model.model_fields)
    for field in model.model_fields.values():
        names.update(_field_input_names(field))
    names.update(getattr(model, "_legacy_input_aliases", frozenset()))
    return names


def _model_types(annotation: Any) -> set[type[BaseModel]]:
    """Enumerar modelos Pydantic referenciados por uma anotação, incluindo uniões e coleções."""
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        found: set[type[BaseModel]] = set()
        for argument in get_args(annotation):
            found.update(_model_types(argument))
        return found
    if origin in (list, set, tuple, frozenset):
        arguments = get_args(annotation)
        return _model_types(arguments[0]) if arguments else set()
    if origin is dict:
        arguments = get_args(annotation)
        return _model_types(arguments[1]) if len(arguments) > 1 else set()
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {annotation}
    return set()


def _select_input_model(
    value: dict[str, Any], candidates: set[type[BaseModel]]
) -> type[BaseModel] | None:
    """Escolher o modelo com maior sobreposição de nomes de entrada."""
    keys = {str(key) for key in value}
    return max(
        candidates,
        key=lambda model: len(keys & _allowed_input_names(model)),
        default=None,
    )


def _field_for_input_name(model: type[BaseModel], name: str) -> FieldInfo | None:
    """Localizar o campo de um modelo que aceita determinado nome de entrada."""
    if name in model.model_fields:
        return model.model_fields[name]
    for field in model.model_fields.values():
        if name in _field_input_names(field):
            return field
    return None


def _collect_model_unknown_fields(
    model: type[BaseModel],
    value: dict[str, Any],
    path: tuple[str | int, ...],
) -> list[tuple[tuple[str | int, ...], str]]:
    """Coletar campos desconhecidos e visitar os valores dos campos conhecidos."""
    allowed = _allowed_input_names(model)
    errors = [
        (path + (str(key),), f"Campo desconhecido: {key}")
        for key in value
        if str(key) not in allowed
    ]
    for key, item in value.items():
        field = _field_for_input_name(model, str(key))
        if field is not None:
            errors.extend(_collect_unknown_fields(field.annotation, item, path + (str(key),)))
    return errors


def _collect_unknown_fields(
    annotation: Any,
    value: Any,
    path: tuple[str | int, ...],
) -> list[tuple[tuple[str | int, ...], str]]:
    """Percorrer o payload comparando sua forma com a anotação do modelo."""
    if isinstance(value, BaseModel):
        return []
    if isinstance(value, dict):
        model = _select_input_model(value, _model_types(annotation))
        return _collect_model_unknown_fields(model, value, path) if model else []
    if isinstance(value, (list, tuple)):
        arguments = get_args(annotation)
        item_annotation = arguments[0] if arguments else Any
        errors: list[tuple[tuple[str | int, ...], str]] = []
        for index, item in enumerate(value):
            errors.extend(_collect_unknown_fields(item_annotation, item, path + (index,)))
        return errors
    return []


def collect_unknown_fields(
    model: type[BaseModel], value: Any
) -> list[tuple[tuple[str | int, ...], str]]:
    """Listar campos desconhecidos em um payload destinado a um modelo de domínio."""
    return _collect_unknown_fields(model, value, ())


class KairosModel(BaseModel):
    """Base comum dos modelos de domínio, com aliases por nome e entrada rigorosa no Backup."""

    model_config = ConfigDict(populate_by_name=True)


class PriceTier(StrEnum):
    """Faixas de preço usadas na Estimativa de Gastos de Hospedagens e Pontos de Interesse."""

    BUDGET = "$"
    MODERATE = "$$"
    COMFORT = "$$$"
    LUXURY = "$$$$"


PriceTierValue = Annotated[PriceTier, BeforeValidator(_parse_enum(PriceTier))]


class FoodProfile(StrEnum):
    """Perfis de gasto diário com alimentação aplicados à Estimativa de Gastos da Viagem."""

    BUDGET = "budget"
    MODERATE = "moderate"
    FINE_DINING = "fine_dining"


class Coordinates(KairosModel):
    """Coordenada geográfica de um Ponto de Interesse ou de uma Hospedagem."""

    latitude: float
    longitude: float

    @classmethod
    def __get_pydantic_json_schema__(cls, _core_schema: Any, handler: Any) -> Any:
        """Personalizar o schema OpenAPI/JSON gerado para representar tupla de floats."""
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
        """Comparar coordenadas por igualdade de latitude e longitude ou tupla equivalente."""
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
        """Serializar coordenadas individualmente em formato numérico float."""
        return value


class TimeWindow(KairosModel):
    """Janela de Disponibilidade ou Janela de Funcionamento com horários de início e fim."""

    start_time: IsoTime = Field(alias="start")
    end_time: IsoTime = Field(alias="end")

    @property
    def start(self) -> time:
        """Obter o horário de início da Janela."""
        return self.start_time

    @property
    def end(self) -> time:
        """Obter o horário de fim da Janela."""
        return self.end_time

    @property
    def duration_minutes(self) -> int:
        """Calcular a duração da janela em minutos, limitada a zero quando invertida."""
        start_min = self.start_time.hour * 60 + self.start_time.minute
        end_min = self.end_time.hour * 60 + self.end_time.minute
        return max(0, end_min - start_min)

    def contains(self, t: time) -> bool:
        """Informar se o horário informado está dentro da janela, inclusive nas bordas."""
        return self.start_time <= t <= self.end_time


class TransportMode(str):
    """Objeto de valor imutável do Modal de Transporte urbano e interurbano."""

    WALKING: ClassVar[TransportMode]
    DRIVING: ClassVar[TransportMode]
    FLYING: ClassVar[TransportMode]
    TRANSIT: ClassVar[TransportMode]

    def __new__(cls, value: str) -> TransportMode:
        """Criar um Modal de Transporte a partir do seu valor textual canônico."""
        return super().__new__(cls, value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """Expor o objeto de valor como um texto validado pelo Pydantic."""
        return core_schema.no_info_after_validator_function(cls, handler(str))


TransportMode.WALKING = TransportMode("walking")
TransportMode.DRIVING = TransportMode("driving")
TransportMode.FLYING = TransportMode("flying")
TransportMode.TRANSIT = TransportMode("transit")


def _parse_transport_mode(value: Any) -> Any:
    """Converta texto legado em objeto de valor do Modal de Transporte."""
    if isinstance(value, str) and not isinstance(value, TransportMode):
        return TransportMode(value)
    return value


TransportModeValue = Annotated[TransportMode, BeforeValidator(_parse_transport_mode)]


class UrbanMode(StrEnum):
    """Modal Urbano de um Dia de Viagem, usado no Deslocamento do Roteiro."""

    WALKING = "walking"
    DRIVING = "driving"


UrbanModeValue = Annotated[UrbanMode, BeforeValidator(_parse_enum(UrbanMode))]


class Accommodation(KairosModel):
    """Hospedagem que serve como Ponto de Partida/Retorno dos Roteiros de um Dia de Viagem."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location: Coordinates
    price_tier: PriceTierValue = PriceTier.MODERATE
    real_daily_rate: Optional[float] = None


class POI(KairosModel):
    """Ponto de Interesse com Janela de Funcionamento, permanência e Pontuação de Utilidade."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location: Coordinates = Field(alias="coordinates")
    window: TimeWindow = Field(
        alias="operating_window",
        default_factory=lambda: TimeWindow(start_time=time(9, 0), end_time=time(18, 0))
    )
    stay_duration_minutes: int = 60
    utility_score: float = 1.0
    category: str = "attraction"
    rating: Optional[float] = None
    price_tier: Optional[PriceTierValue] = None
    awards: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @property
    def operating_window(self) -> TimeWindow:
        """Obter a Janela de Funcionamento do Ponto de Interesse."""
        return self.window

    @property
    def coordinates(self) -> Coordinates:
        """Obter as coordenadas geográficas do Ponto de Interesse."""
        return self.location



class MealSlot(KairosModel):
    """Slot de Refeição do Roteiro com janela, estabelecimentos recomendados e custo estimado."""

    id: str
    name: str
    window: TimeWindow
    recommended_places: list[POI] = Field(default_factory=list)
    selected_place: Optional[POI] = None
    estimated_cost: Optional[float] = None


class ItineraryStop(KairosModel):
    """Ponto de Interesse de um Roteiro com chegada, partida e Deslocamento."""

    poi: POI
    arrival_time: IsoTime
    departure_time: IsoTime
    transit_duration_minutes: int = 0

    @property
    def end(self) -> time:
        """Fim da visita ao POI."""
        return self.departure_time

    @property
    def start(self) -> time:
        """Início da visita ao POI."""
        return self.arrival_time


class RouteStop(KairosModel):
    """Visita a um Ponto de Interesse: ``poi``, ``start`` e Tempo de Permanência."""

    poi: POI = Field(description="Ponto de Interesse visitado.")
    start: IsoDatetime = Field(description="Horário de início da visita ao POI.")
    duration_minutes: int = Field(
        ge=0, description="Tempo de Permanência no POI, em minutos."
    )

    @property
    def end(self) -> datetime:
        """Terceiro do visitante: ``start`` + Tempo de Permanência no POI."""
        return self.start + timedelta(minutes=self.duration_minutes)


class Itinerary(KairosModel):
    """Roteiro ordenado de Pontos de Interesse com Pontuação de Utilidade e duração totais."""

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


class TripDay(KairosModel):
    """Dia de Viagem com Hospedagem, Janela de Disponibilidade, Slots de Refeição e Roteiro."""

    date: IsoDate
    base_accommodation: Accommodation
    custom_accommodation: Optional[Accommodation] = None
    previous_day_accommodation: Optional[Accommodation] = None
    urban_mode: UrbanModeValue = UrbanMode.DRIVING
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


class TripStage(KairosModel):
    """Etapa de Viagem delimitada por cidade e período, composta por Dias de Viagem."""

    id: str = Field(min_length=1)
    city_name: str = Field(min_length=1)
    start_date: IsoDate
    end_date: IsoDate
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


class InterCityConnection(KairosModel):
    """Conexão Interurbana entre Etapas de Viagem com Modal de Transporte e data de partida."""

    _legacy_input_aliases: ClassVar[frozenset[str]] = frozenset({"mode"})

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1)
    from_stage_id: str = ""
    to_stage_id: str = ""
    departure_time: IsoDate | None = None
    departure_datetime: IsoDatetime = Field(description="Partida com data e hora.")
    modal: TransportModeValue = Field(
        default=TransportMode(TransportMode.DRIVING),
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

    @staticmethod
    def _parse_departure_value(dep_time: Any) -> datetime | None:
        """Transformar departure_time legado (datetime, date ou ISO str) em datetime."""
        if isinstance(dep_time, datetime):
            return dep_time
        if isinstance(dep_time, date):
            return datetime.combine(dep_time, time(0, 0))
        if isinstance(dep_time, str):
            try:
                return datetime.fromisoformat(dep_time)
            except ValueError:
                return datetime.combine(date.fromisoformat(dep_time), time(0, 0))
        return None

    @staticmethod
    def _resolve_boarding_cutoff(modal: TransportMode | str | None) -> int:
        """Resolve a Margem de Embarque padrão em minutos para o Modal de Transporte."""
        cutoffs: dict[str, int] = {
            TransportMode.FLYING: 120,
            TransportMode.DRIVING: 30,
            TransportMode.TRANSIT: 30,
        }
        key = str(modal) if modal else TransportMode.DRIVING
        return cutoffs.get(key, 30)

    @model_validator(mode="before")
    @classmethod
    def _apply_modal_default(cls, data: Any) -> Any:
        """Normaliza departure_datetime legado e aplica Margem de Embarque padrão do modal."""
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if normalized.get("departure_datetime") is None:
            parsed_departure = cls._parse_departure_value(normalized.get("departure_time"))
            if parsed_departure is not None:
                normalized["departure_datetime"] = parsed_departure
        if "mode" in normalized:
            legacy_mode = normalized.pop("mode")
            if normalized.get("modal") is None:
                normalized["modal"] = legacy_mode
        if normalized.get("boarding_cutoff_minutes") is None:
            raw_modal = normalized.get("modal")
            modal = raw_modal if isinstance(raw_modal, str) else None
            normalized["boarding_cutoff_minutes"] = cls._resolve_boarding_cutoff(modal)
        return normalized

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

    @property
    def mode(self) -> TransportMode:
        """Projeção legada e somente leitura do Modal de Transporte canônico."""
        return self.modal

    @model_serializer(mode="wrap")
    def serialize_with_legacy_mode(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        """Incluir o campo legado ``mode`` na serialização da Conexão Interurbana."""
        data: dict[str, Any] = handler(self)
        data["mode"] = str(self.modal)
        return data


class PreferencesProfile(KairosModel):
    """Perfil de Preferência com intensidades de 0 a 10 por categoria temática."""

    intensities: dict[str, float] = Field(default_factory=dict)

    def get_intensity(self, category: str) -> float:
        """Obter a intensidade configurada para a categoria, ou zero quando ausente."""
        return self.intensities.get(category, 0.0)

    def set_intensity(self, category: str, value: float) -> None:
        """Definir a intensidade da categoria, limitando o valor ao intervalo de 0 a 10."""
        self.intensities[category] = max(0.0, min(10.0, float(value)))


class CurationList(KairosModel):
    """Lista de Curadoria temática com Pontos de Interesse e indicação de atividade."""

    id: str
    title: str
    description: Optional[str] = None
    items: list[POI] = Field(default_factory=list)
    is_active: bool = True


class Trip(KairosModel):
    """Viagem composta por Etapas de Viagem, Conexões Interurbanas e Perfil de Preferência."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    travelers: int = Field(default=1, ge=1)
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
