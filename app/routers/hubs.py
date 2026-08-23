"""
Router para endpoints de Hubs.
"""
import fcntl
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

router = APIRouter()


class HubCreate(BaseModel):
    """Validation model for POST /hubs."""
    code: str = Field(
        ..., min_length=2, max_length=5,
        description="Hub code: 2-5 alphanumeric characters"
    )
    name: str = Field(
        ..., min_length=1, max_length=100,
        description="Display nomenclature name"
    )
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r"^[A-Z0-9]{2,5}$", v):
            raise ValueError("code must be 2-5 uppercase alphanumeric characters")
        return v

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


def load_hubs():
    """Carga las geolocalizaciones de los hubs desde el archivo JSON."""
    hubs_path = Path(__file__).parent.parent.parent / "hubs.json"
    try:
        with open(hubs_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"hubs": []}

    # Backwards compat: existing hubs without 'name' default to 'code'
    for hub in data.get("hubs", []):
        if "name" not in hub:
            hub["name"] = hub["code"]

    return data


@router.get("/hubs")
def get_hubs():
    """
    Retorna la lista de todos los hubs con sus coordenadas y nombres.
    """
    data = load_hubs()
    return JSONResponse(content=data)


@router.post("/hubs", status_code=201)
def create_hub(payload: HubCreate):
    """
    Create a new hub: validates, checks duplicates, persists to hubs.json.
    Returns 201 with the new hub on success.
    Returns 409 if hub code already exists.
    Uses fcntl.flock for concurrency-safe writes.
    """
    hubs_path = Path(__file__).parent.parent.parent / "hubs.json"

    with open(hubs_path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        try:
            content = f.read()
            data = json.loads(content) if content else {"hubs": []}
        except json.JSONDecodeError:
            data = {"hubs": []}

        # Duplicate check
        for hub in data.get("hubs", []):
            if hub["code"] == payload.code:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "DUPLICATE_HUB_CODE",
                        "field": "code",
                        "message": f"Hub code '{payload.code}' already exists"
                    }
                )

        new_hub = {
            "code": payload.code,
            "name": payload.name,
            "lat": payload.lat,
            "lng": payload.lng,
        }

        data["hubs"].append(new_hub)

        # Write back — truncate first since we opened with r+
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    return JSONResponse(content=new_hub, status_code=201)


@router.get("/hubs/{hub_code}")
def get_hub_by_code(hub_code: str):
    """
    Retorna un hub específico por su código.
    """
    data = load_hubs()
    hub_code = hub_code.upper()

    for hub in data.get("hubs", []):
        if hub["code"] == hub_code:
            return hub

    raise HTTPException(status_code=404, detail=f"Hub '{hub_code}' no encontrado")