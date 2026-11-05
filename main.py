"""Loan Application Service: stores loan applications and scores their default risk."""
from contextlib import asynccontextmanager
import hmac
import os

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from schemas import Application, ApplicationCreate, LoanFeatures, Prediction

ml = {}            # filled at start-up: {"model": ..., "version": ..., "features": [...]}
APPLICATIONS = {}  # in-memory store; resets when the server restarts
MODEL_PATH = os.getenv("MODEL_PATH", "model.joblib")
GIT_SHA = os.getenv("GIT_SHA", "dev")  # set at build time by the pipeline
API_KEY = os.getenv("API_KEY")  # unset locally and in CI: no key needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    ml.update(joblib.load(MODEL_PATH))  # load the model once, when the server starts
    yield
    ml.clear()


app = FastAPI(title="Loan Application Service", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if API_KEY and request.url.path.startswith("/api/"):
        supplied = request.headers.get("x-api-key", "")
        if not hmac.compare_digest(supplied.encode(), API_KEY.encode()):  # constant-time comparison
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid API key"})
    return await call_next(request)


def score(features: LoanFeatures) -> Prediction:
    X = pd.DataFrame([features.model_dump()])[ml["features"]]
    probability = float(ml["model"].predict_proba(X)[0, 1])
    band = "low" if probability < 0.2 else "medium" if probability < 0.5 else "high"
    return Prediction(default_probability=round(probability, 3), risk_band=band, model_version=ml["version"])


@app.get("/health")
def health():
    return {"status": "ok", "model_version": ml.get("version"), "git_sha": GIT_SHA}


@app.post("/api/v1/predictions", response_model=Prediction)
def predict(features: LoanFeatures):
    return score(features)


@app.post("/api/v1/applications", response_model=Application, status_code=201)
def create_application(body: ApplicationCreate):
    new = Application(id=7781 + len(APPLICATIONS), status="pending",
                      prediction=score(body), **body.model_dump())
    APPLICATIONS[new.id] = new
    return new


@app.get("/api/v1/applications", response_model=list[Application])
def list_applications():
    return list(APPLICATIONS.values())


@app.get("/api/v1/applications/{application_id}", response_model=Application)
def get_application(application_id: int):
    if application_id not in APPLICATIONS:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return APPLICATIONS[application_id]
