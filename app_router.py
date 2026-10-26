import logging
import uuid

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from controller.health_controller import router as health_router
from load_env import CORS_ORIGINS, LOG_LEVEL
from utils.logging_config import configure_logging, request_id_ctx

configure_logging(LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ayan API")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Erro não tratado em %s %s", request.method, request.url.path)
        response = JSONResponse(status_code=500, content={"detail": "Erro interno do servidor."})
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(router=health_router, prefix="/health", tags=["health"])

app.include_router(api_router)
