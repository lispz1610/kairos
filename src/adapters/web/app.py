from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.adapters.places import create_places_adapter
from src.core.domain.models import (
    POI,
    Coordinates,
    CurationList,
    Itinerary,
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
link_parser_service = LinkParserService(curation_service=curation_service)


class OptimizeRequest(BaseModel):
    start_location: Coordinates
    end_location: Coordinates
    window: TimeWindow
    candidates: List[POI]
    preferences: Optional[PreferencesProfile] = None


class RippleShiftRequest(BaseModel):
    trip: Trip
    target_stage_id: str
    delta_days: int


class DiningRecommendRequest(BaseModel):
    reference_location: Coordinates
    candidates: List[POI]
    limit: int = 3


class BudgetRequest(BaseModel):
    trip: Trip
    food_profile: str = "moderate"


@app.post("/api/trip/optimize", response_model=Itinerary)
def optimize_trip_day(req: OptimizeRequest) -> Itinerary:
    return solver.solve(
        start_location=req.start_location,
        end_location=req.end_location,
        window=req.window,
        candidates=req.candidates,
        preferences=req.preferences,
    )


@app.post("/api/dining/recommend", response_model=List[POI])
def recommend_dining(req: DiningRecommendRequest) -> List[POI]:
    return dining_service.recommend_meal_places(
        reference_location=req.reference_location,
        candidates=req.candidates,
        limit=req.limit,
    )


@app.post("/api/trip/budget", response_model=BudgetSummary)
def calculate_budget(req: BudgetRequest) -> BudgetSummary:
    return dining_service.calculate_trip_budget(
        trip=req.trip,
        food_profile=req.food_profile,
    )


@app.post("/api/trip/ripple-shift/preview", response_model=RippleShiftPreview)
def preview_ripple_shift(req: RippleShiftRequest) -> RippleShiftPreview:
    return schedule_service.preview_ripple_shift(
        trip=req.trip,
        target_stage_id=req.target_stage_id,
        delta_days=req.delta_days,
    )


@app.post("/api/trip/ripple-shift/apply", response_model=Trip)
def apply_ripple_shift(req: RippleShiftRequest) -> Trip:
    return schedule_service.apply_ripple_shift(
        trip=req.trip,
        target_stage_id=req.target_stage_id,
        delta_days=req.delta_days,
    )


@app.post("/api/trip/export-markdown")
def export_trip_markdown(trip: Trip) -> dict[str, str]:
    md = markdown_service.export_trip_markdown(trip)
    return {"markdown": md}


@app.get("/api/curation/suggested", response_model=List[CurationList])
def get_suggested_curation(city_name: str) -> List[CurationList]:
    return curation_service.get_suggested_curation_lists(city_name)


@app.get("/api/places/search", response_model=List[POI])
def search_places(query: str, city_name: Optional[str] = None) -> List[POI]:
    return curation_service.search_places_autocomplete(query, city_name)


class ImportLinkRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    city_name: Optional[str] = None


@app.post("/api/curation/import-link")
def import_curation_link(req: ImportLinkRequest) -> dict[str, List[POI]]:
    content = req.text or ""
    if req.url:
        try:
            content = link_parser_service.fetch_url_content(req.url)
        except SSRFValidationError as err:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=str(err))
        except Exception as err:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Erro ao acessar URL: {err}")

    if not content:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Forneça uma 'url' ou 'text' para importação.")

    candidates = link_parser_service.extract_places_from_text(content, req.city_name)
    return {"candidates": candidates}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "app": "kairos"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "Kairos — Traçador Dinâmico de Rotas Turísticas"},
    )
