
"""FastAPI application entry point."""

from fastapi import FastAPI

from api.routers.notams import router as notams_router  # Person A: GET /notams/*
from api.routers.plan import router as plan_router  # routing: POST /plan
from api.schemas import HealthResponse

app = FastAPI(
    title="NOTAM-Aware Route Planning API",
    description="Research API for route-aware NOTAM intelligence. "
    "Decision support for research only; not for operational use.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness check that does not require a database connection."""
    return HealthResponse(
        status="ok",
        database="not_checked",
    )


app.include_router(notams_router)
app.include_router(plan_router)
