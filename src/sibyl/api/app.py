from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from sibyl.dependency_analysis.api import router as dependency_analysis_router
from sibyl.engineering_metrics.api import router as engineering_metrics_router
from sibyl.ingestion.api import router as ingestion_router
from sibyl.ingestion.coverage_api import router as coverage_router
from sibyl.ingestion.dependency_api import router as dependency_router
from sibyl.ingestion.test_results_api import router as test_results_router
from sibyl.platform.config import Settings, get_settings
from sibyl.platform.db import make_session_factory
from sibyl.platform.errors import ProblemException
from sibyl.platform.observability import configure_observability
from sibyl.pr_analysis.api import router as pr_analysis_router
from sibyl.regression_prediction.api import router as regression_prediction_router
from sibyl.root_cause_analysis.api import router as root_cause_analysis_router
from sibyl.test_intelligence.api import router as test_intelligence_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    app.state.session_factory = make_session_factory(settings)
    app.state.redis = Redis.from_url(settings.redis_url)
    yield
    await app.state.redis.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_observability("sibyl-api", settings)

    app = FastAPI(title="Sibyl API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    app.include_router(ingestion_router)
    app.include_router(test_results_router)
    app.include_router(coverage_router)
    app.include_router(dependency_router)
    app.include_router(pr_analysis_router)
    app.include_router(test_intelligence_router)
    app.include_router(root_cause_analysis_router)
    app.include_router(dependency_analysis_router)
    app.include_router(regression_prediction_router)
    app.include_router(engineering_metrics_router)

    @app.exception_handler(ProblemException)
    async def problem_exception_handler(request: Request, exc: ProblemException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.problem,
            media_type="application/problem+json",
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        async with app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        await app.state.redis.ping()
        return {"status": "ready"}

    return app
