from pathlib import Path
from typing import List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.core.domain.models import POI, Coordinates, Itinerary, TimeWindow
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


class OptimizeRequest(BaseModel):
    start_location: Coordinates
    end_location: Coordinates
    window: TimeWindow
    candidates: List[POI]


@app.post("/api/trip/optimize", response_model=Itinerary)
def optimize_trip_day(req: OptimizeRequest) -> Itinerary:
    return solver.solve(
        start_location=req.start_location,
        end_location=req.end_location,
        window=req.window,
        candidates=req.candidates,
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
