from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import Base, engine
from app.core.rate_limit import limiter
from app.routers import alertas, auth, clima, previsao

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vinícola API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.environment == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clima.router)
app.include_router(alertas.router)
app.include_router(previsao.router)


@app.get("/health")
def health():
    return {"status": "ok"}