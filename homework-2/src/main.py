from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.database import init_db
from src.routers.tickets import router as tickets_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    init_db()
    yield


app = FastAPI(
    title="Customer Support Ticket API",
    description="Multi-format ticket management system with CSV/JSON/XML import.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(tickets_router)
