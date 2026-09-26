import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api import analysis, deployments, projects, system
from app.core.config import settings
from app.db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("deploymind")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting DeployMind")
    init_db()
    logger.info("Database ready")
    try:
        from app.services.kubernetes import prepare_kubeconfig

        prepare_kubeconfig()
    except Exception:
        logger.warning("kubeconfig not prepared yet (kind may be missing)")
    yield


app = FastAPI(title="CodeDeck", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if not origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(analysis.router)
app.include_router(deployments.router)
app.include_router(system.router)


@app.get("/")
def root():
    return JSONResponse(
        {
            "service": "deploymind",
            "status": "ok",
            "docs": "/docs",
            "health": "/health",
        }
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/health")
def health():
    return {"status": "ok", "service": "deploymind"}
