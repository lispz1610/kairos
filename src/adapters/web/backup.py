from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from src.core.domain.models import Trip, collect_unknown_fields


def _validation_error(loc: tuple[str | int, ...], message: str, kind: str) -> dict[str, Any]:
    """Montar um erro de validação no formato usado pelo FastAPI."""
    return {"loc": list(loc), "msg": message, "type": kind}


def validate_backup_payload(payload: Any) -> Trip:
    """Validar um Backup JSON com o contrato da Viagem e campos extras proibidos."""
    errors = [
        _validation_error(loc, message, "extra_forbidden")
        for loc, message in collect_unknown_fields(Trip, payload)
    ]
    trip: Trip | None = None
    try:
        trip = Trip.model_validate(payload, strict=True)
    except ValidationError as exc:
        errors.extend(
            _validation_error(
                tuple(str(item) for item in error["loc"]),
                error["msg"],
                error["type"],
            )
            for error in exc.errors()
        )
    if errors or trip is None:
        raise HTTPException(status_code=422, detail=errors)
    return trip
