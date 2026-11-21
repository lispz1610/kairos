from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.adapters.http.safe_fetcher import SafeHttpFetcher
from src.adapters.places import create_places_adapter
from src.core.domain.models import (
    POI,
    Coordinates,
    CurationList,
    Itinerary,
    MealSlot,
    PreferencesProfile,
    TimeWindow,
    Trip,
)
from src.core.services.curation import CurationService
from src.core.services.dining_and_budget import BudgetSummary, DiningService
from src.core.services.link_parser import LinkParserService, SSRFValidationError
from src.core.services.markdown_export import MarkdownExportService
from src.core.services.schedule import RippleShiftPreview, ScheduleService
from src.core.solvers.optw import OPTWSolver

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(
    title="Kairos — Traçador Dinâmico de Rotas Turísticas",
    description="Sistema de recomendação e otimização de itinerários turísticos multicidades.",
    version="0.1.0",
)

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

solver = OPTWSolver()
schedule_service = ScheduleService()
dining_service = DiningService()
markdown_service = MarkdownExportService()
places_adapter = create_places_adapter()
curation_service = CurationService(places_port=places_adapter)
link_parser_service = LinkParserService(
    fetcher=SafeHttpFetcher(), curation_service=curation_service
)


class OptimizeRequest(BaseModel):
    """Corpo da requisição de otimização do Roteiro de um Dia de Viagem."""

    start_location: Coordinates
    end_location: Coordinates
    window: TimeWindow
    candidates: List[POI]
    preferences: Optional[PreferencesProfile] = None
    reserved_slots: Optional[List[TimeWindow]] = None
    curation_lists: Optional[List[CurationList]] = None


class RippleShiftRequest(BaseModel):
    """Corpo da requisição de prévia ou aplicação de Deslocamento em Cascata."""

    trip: Trip
    target_stage_id: str
    delta_days: int


class DiningRecommendRequest(BaseModel):
    """Corpo da requisição de recomendação de estabelecimentos gastronômicos."""

    reference_location: Coordinates
    candidates: List[POI]
    limit: int = 3
    curation_lists: Optional[List[CurationList]] = None


class ContextualDiningRequest(BaseModel):
    """Corpo da requisição de geração de Slots de Refeição contextuais para o Roteiro."""

    departure_location: Coordinates
    return_location: Coordinates
    restaurant_candidates: List[POI]
    itinerary: Optional[Itinerary] = None
    preferences: Optional[PreferencesProfile] = None
    cafe_candidates: Optional[List[POI]] = None
    wine_candidates: Optional[List[POI]] = None
    curation_lists: Optional[List[CurationList]] = None


class BudgetRequest(BaseModel):
    """Corpo da requisição de cálculo da Estimativa de Gastos da viagem."""

    trip: Trip
    food_profile: str = "moderate"


@app.post("/api/trip/optimize", response_model=Itinerary)
def optimize_trip_day(req: OptimizeRequest) -> Itinerary:
    """Otimiza a sequência de visitas para um dia de viagem via algoritmo OPTW."""
    candidates = req.candidates
    if req.curation_lists:
        candidates = curation_service.apply_curation_boost(
            candidates, req.curation_lists
        )
    return solver.solve(
        start_location=req.start_location,
        end_location=req.end_location,
        window=req.window,
        candidates=candidates,
        preferences=req.preferences,
        reserved_slots=req.reserved_slots,
    )


@app.post("/api/dining/recommend", response_model=List[POI])
def recommend_dining(req: DiningRecommendRequest) -> List[POI]:
    """Recomenda estabelecimentos gastronômicos com base na proximidade e curadoria."""
    candidates = req.candidates
    if req.curation_lists:
        candidates = curation_service.apply_curation_boost(
            candidates, req.curation_lists
        )
    return dining_service.recommend_meal_places(
        reference_location=req.reference_location,
        candidates=candidates,
        limit=req.limit,
    )


@app.post("/api/dining/contextual-slots", response_model=List[MealSlot])
def get_contextual_meal_slots(req: ContextualDiningRequest) -> List[MealSlot]:
    """Gera slots contextuais de refeição e pausas temáticas para o roteiro diário."""
    restaurants = req.restaurant_candidates
    cafes = req.cafe_candidates
    wines = req.wine_candidates
    if req.curation_lists:
        restaurants = curation_service.apply_curation_boost(
            restaurants, req.curation_lists
        )
        if cafes:
            cafes = curation_service.apply_curation_boost(
                cafes, req.curation_lists
            )
        if wines:
            wines = curation_service.apply_curation_boost(
                wines, req.curation_lists
            )
    return dining_service.create_contextual_meal_slots(
        departure_location=req.departure_location,
        return_location=req.return_location,
        restaurant_candidates=restaurants,
        itinerary=req.itinerary,
        preferences=req.preferences,
        cafe_candidates=cafes,
        wine_candidates=wines,
    )


@app.post("/api/trip/budget", response_model=BudgetSummary)
def calculate_budget(req: BudgetRequest) -> BudgetSummary:
    """Calcula o resumo orçamentário consolidado da viagem considerando hospedagem e refeições."""
    return dining_service.calculate_trip_budget(
        trip=req.trip,
        food_profile=req.food_profile,
    )


@app.post("/api/trip/ripple-shift/preview", response_model=RippleShiftPreview)
def preview_ripple_shift(req: RippleShiftRequest) -> RippleShiftPreview:
    """Gera prévia das alterações de datas decorrentes do deslocamento em cascata."""
    return schedule_service.preview_ripple_shift(
        trip=req.trip,
        target_stage_id=req.target_stage_id,
        delta_days=req.delta_days,
    )


@app.post("/api/trip/ripple-shift/apply", response_model=Trip)
def apply_ripple_shift(req: RippleShiftRequest) -> Trip:
    """Aplica o deslocamento em cascata nas etapas e conexões da viagem."""
    return schedule_service.apply_ripple_shift(
        trip=req.trip,
        target_stage_id=req.target_stage_id,
        delta_days=req.delta_days,
    )


@app.post("/api/trip/export-markdown")
def export_trip_markdown(trip: Trip) -> dict[str, str]:
    """Exporta a viagem completa em formato Markdown estruturado."""
    md = markdown_service.export_trip_markdown(trip)
    return {"markdown": md}


@app.get("/api/curation/suggested", response_model=List[CurationList])
def get_suggested_curation(city_name: str) -> List[CurationList]:
    """Retorna listas de curadoria sugeridas para uma cidade informada."""
    return curation_service.get_suggested_curation_lists(city_name)


@app.get("/api/places/search", response_model=List[POI])
def search_places(query: str, city_name: Optional[str] = None) -> List[POI]:
    """Busca pontos de interesse com suporte a autocomplete e filtro por cidade."""
    return curation_service.search_places_autocomplete(query, city_name)


class ImportLinkRequest(BaseModel):
    """Corpo da requisição de importação de curadoria a partir de URL ou texto."""

    url: Optional[str] = None
    text: Optional[str] = None
    city_name: Optional[str] = None


@app.post("/api/curation/import-link")
def import_curation_link(req: ImportLinkRequest) -> dict[str, List[POI]]:
    """Importa candidatos a pontos de interesse a partir de link ou texto com proteção SSRF."""
    content = req.text or ""
    if req.url:
        try:
            content = link_parser_service.fetch_url_content(req.url)
        except SSRFValidationError as err:
            raise HTTPException(status_code=400, detail=str(err))
        except Exception as err:
            raise HTTPException(status_code=400, detail=f"Erro ao acessar URL: {err}")

    if not content:
        raise HTTPException(status_code=400, detail="Forneça uma 'url' ou 'text' para importação.")

    candidates = link_parser_service.extract_places_from_text(content, req.city_name)
    return {"candidates": candidates}


@app.get("/health")
def health_check() -> dict[str, str]:
    """Retorna o status operacional da aplicação."""
    return {"status": "ok", "app": "kairos"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Renderiza a página principal da interface web da aplicação."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "Kairos — Traçador Dinâmico de Rotas Turísticas"},
    )
