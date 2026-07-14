import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.core.exceptions import DuplicateResourceException, ResourceNotFoundException
from app.core.messaging.rabbitmq import close_rabbitmq, connect_rabbitmq
from app.routers import auth, oauth, verification, chat, events, webhooks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.use_sqlite:
        # Sqlite is for convenience. 
        # Real (MySQL) schema changes go through Alembic instead: `alembic upgrade head`.
        Base.metadata.create_all(bind=engine)

    await connect_rabbitmq()
    try:
        yield
    finally:
        await close_rabbitmq()


app = FastAPI(
    title="Centry API",
    description="SAGE Centry - Base Authentication, User Schema, Platform OAuth, "
                 "Live Voice Verification, Real-Time Dashboard Events & Centry AI Chatbot",
    version="0.4.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(verification.router)
app.include_router(chat.router)
app.include_router(events.router)
app.include_router(webhooks.router)


@app.exception_handler(DuplicateResourceException)
async def duplicate_handler(request: Request, exc: DuplicateResourceException):
    return JSONResponse(status_code=409, content={"message": exc.message})


@app.exception_handler(ResourceNotFoundException)
async def not_found_handler(request: Request, exc: ResourceNotFoundException):
    return JSONResponse(status_code=404, content={"message": exc.message})


@app.get("/health")
def health_check():
    return {"status": "ok"}
