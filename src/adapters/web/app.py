from pathlib import Path
from typing import List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.core.domain.models import POI, Coordinates, Itinerary, TimeWindow, Trip
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


class OptimizeRequest(BaseModel):
    start_location: Coordinates
    end_location: Coordinates
    window: TimeWindow
    candidates: List[POI]


class RippleShiftRequest(BaseModel):
    trip: Trip
    target_stage_id: str
    delta_days: int


@app.post("/api/trip/optimize", response_model=Itinerary)
def optimize_trip_day(req: OptimizeRequest) -> Itinerary:
    return solver.solve(
        start_location=req.start_location,
        end_location=req.end_location,
        window=req.window,
        candidates=req.candidates,
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
