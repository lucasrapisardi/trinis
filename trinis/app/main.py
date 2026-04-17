from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import engine, Base
from app.api.routes import auth
from app.api.routes import stores
from app.api.routes import jobs
from app.api.routes import billing
from app.api.routes import tenant
from app.api.routes import products
from app.api.routes import password_reset
from app.api.routes import team

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="ProductSync API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

origins = (
    ["*"] if settings.app_env == "development"
    else [settings.app_base_url, "https://app.productsync.io"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(stores.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(tenant.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(password_reset.router, prefix="/api")
app.include_router(team.router, prefix="/api")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "env": settings.app_env}
