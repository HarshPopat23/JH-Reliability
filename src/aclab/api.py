"""Local experiment API. No arbitrary URLs, credentials, actors or real actions in requests."""
import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from .cli import load_config
from .runner import Runner
from .sandbox import tasks
from .types import ExperimentConfig, StrictModel


class RunRequest(StrictModel):
    task_index: int = Field(default=0, ge=0, le=71)
    profile: str = Field(default="mock", max_length=64)


@asynccontextmanager
async def lifespan(app):
    profiles = {"mock": ExperimentConfig()}
    directory = os.environ.get("ACLAB_PROFILE_DIR")
    if directory:
        for path in Path(directory).glob("*.yaml"):
            if path.stem == "mock":
                raise ValueError("The mock profile name is reserved for the built-in scripted service")
            profiles[path.stem] = load_config(path)
    app.state.limit = int(os.environ.get("ACLAB_MAX_ACTIVE", "16"))
    if not 1 <= app.state.limit <= 1024:
        raise ValueError("ACLAB_MAX_ACTIVE must be between 1 and 1024")
    app.state.runners = {name: Runner(config) for name, config in profiles.items()}
    app.state.active = 0
    app.state.requests = 0
    app.state.rejected = 0
    try:
        yield
    finally:
        for runner in app.state.runners.values():
            await runner.close()


app = FastAPI(title="Agent Contract Lab — sandbox experiments", lifespan=lifespan)


@app.middleware("http")
async def body_limit(request: Request, call_next):
    if request.method == "POST":
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 8192:
                return JSONResponse({"detail": "Request exceeds 8192 bytes"}, status_code=413)
        request._body = bytes(data)
    return await call_next(request)


def authorize(authorization):
    expected = os.environ.get("ACLAB_API_KEY")
    if expected and not secrets.compare_digest(authorization or "", "Bearer " + expected):
        raise HTTPException(401, "Missing or invalid experiment API key")


@app.get("/health")
async def health():
    return {"status": "ok", "scope": "sandbox-only"}


@app.get("/metrics")
async def metrics(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return {"requests": app.state.requests, "active": app.state.active, "rejected": app.state.rejected, "per_worker_limit": app.state.limit}


@app.post("/run")
async def run(body: RunRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    runner = app.state.runners.get(body.profile)
    if runner is None:
        raise HTTPException(404, "Unknown server-configured profile")
    if app.state.active >= app.state.limit:
        app.state.rejected += 1
        raise HTTPException(429, "Worker is at capacity", headers={"Retry-After": "1"})
    app.state.active += 1
    app.state.requests += 1
    try:
        # Actor and approval come only from server-owned fixtures, never request JSON.
        return await runner.run(tasks(72, runner.config.seed)[body.task_index])
    finally:
        app.state.active -= 1
