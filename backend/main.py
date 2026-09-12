from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from parts_library import (
    validate_model,
    default_repressilator_model,
    default_toggle_model,
    incoherent_feedforward_loop_model,
)
from simulator import simulate, diff_traces

app = FastAPI(title="BioCompiler API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ModelRequest(BaseModel):
    parts: list[dict]
    edges: list[dict]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/circuits/{name}")
def get_default_circuit(name: str):
    catalog = {
        "repressilator": default_repressilator_model,
        "toggle": default_toggle_model,
        "feedforward": incoherent_feedforward_loop_model,
    }
    if name not in catalog:
        raise HTTPException(status_code=404, detail=f"Unknown circuit '{name}'. Options: {list(catalog.keys())}")
    return catalog[name]()


@app.post("/simulate")
def run_simulation(model: ModelRequest):
    model_dict = model.model_dump()
    ok, msg = validate_model(model_dict)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Model rejected by whitelist: {msg}")
    try:
        result = simulate(model_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {e}")
    return result


@app.post("/diff")
def run_diff(payload: dict):
    if "before" not in payload or "after" not in payload:
        raise HTTPException(status_code=400, detail="Payload must contain 'before' and 'after' simulation results")
    return diff_traces(payload["before"], payload["after"])