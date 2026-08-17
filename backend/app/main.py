from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.config import settings
from app.db import init_db
from app.routes.generate import router as generate_router
from app.routes.eval import router as eval_router
from app.routes.products import router as products_router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Grounded Product Copy Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catches anything not already handled by a specific route (e.g. DB
    connection failure, an unexpected bug). Logs the real error server-side
    for debugging, but returns a generic message to the caller — never
    leak internal stack traces or DB connection strings in a response."""
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again or contact support."},
    )


app.include_router(generate_router)
app.include_router(eval_router)
app.include_router(products_router)


@app.get("/health")
def health():
    return {"status": "ok"}