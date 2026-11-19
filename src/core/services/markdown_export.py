from __future__ import annotations

from typing import List, Optional

from src.core.domain.models import CurationList, Itinerary, MealSlot, Trip, TripDay, TripStage
from src.core.services.dining_and_budget import BudgetSummary, DiningService


class MarkdownExportService:
    """Gera guias de viagem detalhados e estruturados em GitHub Flavored Markdown (GFM)."""

    def __init__(self) -> None:
        self.dining_service = DiningService()

    def export_trip_markdown(
        self, trip: Trip, budget: Optional[BudgetSummary] = None
    ) -> str:
        """Exporta os dados estruturados da viagem em formato GitHub Flavored Markdown."""
        for stage in trip.stages:
            stage._relink_accommodations()

        if budget is None:
            budget = self.dining_service.calculate_trip_budget(trip)

        sections: List[str] = [
            self._render_header(trip),
            self._render_budget_table(budget),
            self._render_stages(trip.stages),
            self._render_curation_appendix(trip.curation_lists),
        ]
        return "\n\n".join(sections)

    def _render_header(self, trip: Trip) -> str:
        lines: List[str] = [
            f"# 🌍 {trip.title}",
            "",
            (
                "> **Kairos Travel Guide** — "
                "Guia estruturado de viagem gerado dinamicamente com curadoria."
            ),
            "",
            f"- 👥 **Viajantes**: {trip.travelers} pessoa(s)",
            "",
            "### 📌 Resumo da Jornada",
        ]
        if trip.notes:
            lines.insert(5, f"- 📝 **Notas Pessoais**: {trip.notes}")
        for st in trip.stages:
            s_date = st.start_date.strftime("%d/%m/%Y")
            e_date = st.end_date.strftime("%d/%m/%Y")
            lines.append(f"- **{st.city_name}**: {s_date} a {e_date} ({len(st.days)} dias)")
        for conn in trip.connections:
            d_time = conn.departure_time.strftime("%d/%m/%Y")
            lines.append(
                f"- ✈️ **Conexão Interurbana**: Partida em {d_time} (Modal: `{conn.mode.value}`)"
            )
        return "\n".join(lines)

    def _render_budget_table(self, budget: BudgetSummary) -> str:
        lines: List[str] = [
            "## 💰 Quadro Orçamentário Estimado",
            "",
            "| Etapa / Cidade | Dias | Hospedagem | Alimentação Estimada | Subtotal |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ]
        for stage_id, breakdown in budget.stage_breakdowns.items():
            lines.append(
                f"| `{stage_id}` | {breakdown.days_count} | "
                f"R$ {breakdown.accommodation_cost:.2f} | "
                f"R$ {breakdown.dining_cost:.2f} | R$ {breakdown.total_cost:.2f} |"
            )
        lines.append(
            f"| **TOTAL** | - | **R$ {budget.total_accommodation_cost:.2f}** | "
            f"**R$ {budget.total_dining_cost:.2f}** | **R$ {budget.total_trip_cost:.2f}** |"
        )
        return "\n".join(lines)

    def _render_stages(self, stages: List[TripStage]) -> str:
        lines: List[str] = ["## 📅 Caderno Diário Detalhado"]
        for st in stages:
            s_date = st.start_date.strftime("%d/%m/%Y")
            e_date = st.end_date.strftime("%d/%m/%Y")
            hotel = st.base_accommodation
            lines.append(f"\n### 📍 {st.city_name}")
            lines.append(
                f"**Período**: {s_date} a {e_date} | "
                f"**Hospedagem Base**: {hotel.name} ({hotel.price_tier})"
            )
            for idx, day in enumerate(st.days):
                lines.append(self._render_day(day, idx + 1))
        return "\n".join(lines)

    def _render_day(self, day: TripDay, day_num: int) -> str:
        badge = " ⚠️ *[Dia de Troca de Hospedagem]*" if day.is_transition_day else ""
        d_str = day.date.strftime("%d/%m/%Y")
        w_start = day.availability_window.start_time.strftime("%H:%M")
        w_end = day.availability_window.end_time.strftime("%H:%M")
        lines: List[str] = [
            f"\n#### Dia {day_num} — {d_str}{badge}",
            f"- 🛌 **Hospedagem Ativa**: {day.effective_accommodation.name}",
            f"- 🚪 **Partida**: {day.departure_accommodation.name} | "
            f"🏁 **Retorno**: {day.return_accommodation.name}",
            f"- ⏰ **Janela**: {w_start} às {w_end}",
            "",
            "**Cronograma de Visitas & Refeições:**",
        ]
        lines.extend(self._render_itinerary_stops(day.itinerary))
        if day.is_transition_day and day.include_luggage_dropoff:
            lines.append(
                f"  - 🧳 `16:00`: **Check-in e Parada de Malas** ({day.return_accommodation.name})"
            )
        lines.extend(self._render_meal_slots(day.meal_slots))
        return "\n".join(lines)

    def _render_itinerary_stops(self, itinerary: Optional[Itinerary]) -> List[str]:
        if not itinerary or not itinerary.stops:
            return ["  - *Dia livre ou aguardando otimização do roteiro.*"]

        result: List[str] = []
        for stop in itinerary.stops:
            awards_str = f" [Selos: {', '.join(stop.poi.awards)}]" if stop.poi.awards else ""
            arr = stop.arrival_time.strftime("%H:%M")
            dep = stop.departure_time.strftime("%H:%M")
            dur = stop.poi.stay_duration_minutes
            transit = (
                f" [Deslocamento: {stop.transit_duration_minutes} min]"
                if stop.transit_duration_minutes > 0
                else ""
            )
            result.append(
                f"  - `{arr} – {dep}`: **{stop.poi.name}** ({dur} min){transit}{awards_str}"
            )
        return result

    def _render_meal_slots(self, meal_slots: List[MealSlot]) -> List[str]:
        result: List[str] = []
        for slot in meal_slots:
            place = slot.selected_place
            place_name = place.name if place else "A escolher na proximidade"
            awards_str = f" ({', '.join(place.awards)})" if place and place.awards else ""
            cost_str = f" [~R$ {slot.estimated_cost:.2f}]" if slot.estimated_cost else ""
            s_arr = slot.window.start_time.strftime("%H:%M")
            s_dep = slot.window.end_time.strftime("%H:%M")
            slot_label = f"🍽️ `{s_arr} – {s_dep}`: **{slot.name}**"
            result.append(f"  - {slot_label} — {place_name}{awards_str}{cost_str}")
        return result

    def _render_curation_appendix(self, curation_lists: List[CurationList]) -> str:
        lines: List[str] = [
            "## 🏆 Apêndice de Curadoria & Recomendações",
            "",
            "> Estabelecimentos chancelados por premiações e listas personalizadas do viajante.",
        ]
        if not curation_lists:
            lines.append("- *Nenhuma lista temática adicional cadastrada.*")
            return "\n".join(lines)

        for cur_list in curation_lists:
            lines.append(f"\n### ⭐ {cur_list.title}")
            if cur_list.description:
                lines.append(f"*{cur_list.description}*")
            for item in cur_list.items:
                awards_str = f" ({', '.join(item.awards)})" if item.awards else ""
                lines.append(f"- **{item.name}** — {item.category}{awards_str}")

        return "\n".join(lines)
