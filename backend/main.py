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
from ai_operator import edit_circuit, explain_diff

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


class EditRequest(BaseModel):
    instruction: str
    current_model: ModelRequest


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


@app.post("/edit_and_explain")
def edit_and_explain(req: EditRequest):
    """
    The actual core loop: NL instruction -> AI edits model -> resimulate ->
    diff -> AI explains. This is the one endpoint that makes the whole
    project's USP literally true, rather than a chart with preset buttons.
    """
    current_model = req.current_model.model_dump()

    ok, msg = validate_model(current_model)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Current model rejected by whitelist: {msg}")

    try:
        before = simulate(current_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulating current model failed: {e}")

    try:
        edited_model, substitution_note = edit_circuit(req.instruction, current_model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI operator call failed: {e}")

    try:
        after = simulate(edited_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulating edited model failed: {e}")

    diff = diff_traces(before, after)

    try:
        explanation = explain_diff(req.instruction, diff, substitution_note)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI explainer call failed: {e}")

    return {
        "edited_model": edited_model,
        "before": before,
        "after": after,
        "diff": diff,
        "substitution_note": substitution_note,
        "explanation": explanation,
    }