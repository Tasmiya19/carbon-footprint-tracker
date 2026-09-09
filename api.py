"""
api.py

FastAPI backend layer for the Carbon Footprint Tracker's Electricity Bill
module. This wraps the EXISTING, already-tested logic in
carbon_calculator.py, ocr_parser.py, and database.py -- it does not
reimplement any calculation or OCR logic, just exposes it as HTTP
endpoints, matching the API design sketched in the project report.

This lets other clients (a future web frontend, a mobile app, Power BI's
web connector, curl/Postman, etc.) use the same core logic that the
Streamlit app uses, without needing to run Streamlit.

Run with:
    pip install fastapi uvicorn python-multipart
    uvicorn api:app --reload

Then open http://127.0.0.1:8000/docs for interactive API documentation
(FastAPI generates this automatically).
"""

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from carbon_calculator import build_result, EMISSION_FACTOR_KG_PER_KWH
from database import (
    init_db,
    save_record,
    get_all_records,
    get_records_for_user,
    get_leaderboard,
    create_user,
    verify_user,
)

try:
    from ocr_parser import extract_units_consumed
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


app = FastAPI(
    title="Carbon Footprint Tracker API",
    description="API layer for the Electricity Bill module -- calculation, OCR, and history.",
    version="1.0.0",
)

# Allow requests from any origin (e.g. a separate frontend running on a
# different port) -- fine for a student project; a production system
# would restrict this to known origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------

class CalculateRequest(BaseModel):
    units_consumed: float
    user_name: str = "Guest"
    save_to_history: bool = True


class CalculateResponse(BaseModel):
    electricityUnits: float
    carbonEmission: str
    ecoScore: int
    recommendation: str


class SignupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Root / health check
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Carbon Footprint Tracker API",
        "emission_factor_kg_per_kwh": EMISSION_FACTOR_KG_PER_KWH,
        "ocr_available": OCR_AVAILABLE,
        "docs": "/docs",
    }


# ---------------------------------------------------------------------------
# Electricity Bill endpoints
# ---------------------------------------------------------------------------

@app.post("/api/electricity/calculate", response_model=CalculateResponse)
def calculate_emission(request: CalculateRequest):
    """
    Calculate carbon emission, eco-score, and recommendation for a given
    number of electricity units consumed. Optionally saves the result to
    history (same ActivityData table the Streamlit app uses).
    """
    if request.units_consumed < 0:
        raise HTTPException(status_code=400, detail="units_consumed cannot be negative")

    result = build_result(request.units_consumed)

    if request.save_to_history:
        emission_value = float(result["carbonEmission"].split(" ")[0])
        save_record(
            user_name=request.user_name,
            electricity_units=request.units_consumed,
            carbon_emission_kg=emission_value,
            eco_score=result["ecoScore"],
            recommendation=result["recommendation"],
        )

    return result


@app.post("/api/electricity/scan")
async def scan_bill(file: UploadFile = File(...)):
    """
    Upload a bill image and extract the units consumed via OCR, using the
    exact same extraction logic (pattern matching -> meter-reading
    fallback -> candidate list) as the Streamlit app's upload/camera flow.

    Returns:
        - {"units": <number>, "candidates": []} if a value was confidently extracted
        - {"units": None, "candidates": [...]} if OCR found numbers but couldn't
          confirm which one is correct (caller should ask the user to pick)
    """
    if not OCR_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="OCR is not available on this server (Tesseract not installed).",
        )

    # Save the uploaded file to a temp path -- our OCR functions work on
    # file paths, matching how the Streamlit app calls them.
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    units, candidates = extract_units_consumed(tmp_path)
    return {"units": units, "candidates": candidates}


@app.get("/api/electricity/history/{username}")
def get_history(username: str):
    """Return all saved entries for one user, most recent first."""
    records = get_records_for_user(username)
    return [
        {
            "id": r[0],
            "user": r[1],
            "units_kwh": r[2],
            "emission_kg_co2": r[3],
            "eco_score": r[4],
            "recommendation": r[5],
            "created_at": r[6],
        }
        for r in records
    ]


@app.get("/api/electricity/history")
def get_all_history():
    """Return every saved entry across all users, most recent first."""
    records = get_all_records()
    return [
        {
            "id": r[0],
            "user": r[1],
            "units_kwh": r[2],
            "emission_kg_co2": r[3],
            "eco_score": r[4],
            "recommendation": r[5],
            "created_at": r[6],
        }
        for r in records
    ]


@app.get("/api/leaderboard")
def leaderboard(limit: int = 10):
    """Return the top users ranked by total points (summed eco-score)."""
    rows = get_leaderboard(limit=limit)
    return [
        {"user": r[0], "avg_eco_score": r[1], "total_points": r[2], "entries": r[3]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Auth endpoints (matching the Streamlit app's login/signup)
# ---------------------------------------------------------------------------

@app.post("/api/auth/signup")
def signup(request: SignupRequest):
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    success = create_user(request.username, request.password)
    if not success:
        raise HTTPException(status_code=409, detail="Username already taken.")
    return {"status": "created", "username": request.username}


@app.post("/api/auth/login")
def login(request: LoginRequest):
    if verify_user(request.username, request.password):
        return {"status": "ok", "username": request.username}
    raise HTTPException(status_code=401, detail="Incorrect username or password.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
