"""FastAPI read-only API for macro event SQLite database."""
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from apps.api.dependencies import get_context
from apps.api.routes import events, search

app = FastAPI(
    title="Macro Maintainer API",
    description="Read-only API over 3-table SQLite event store",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(search.router)


@app.on_event("startup")
async def startup_event() -> None:
    get_context().store.initialize()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
