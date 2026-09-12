"""
BioCompiler parts library, v2 — graph-general.

The old v1 schema hardcoded two shapes: "ring" and "mutual". This version
removes topology as a concept entirely. A circuit is just:
  - a list of gene instances (any number, any names you choose)
  - a list of directed regulatory edges between them, each either
    "repress" or "activate"

WHAT IS BOUNDED (on purpose, non-negotiable):
Only two regulatory MECHANISM TYPES are whitelisted, because only these two
have well-established, published Hill-function kinetic forms:
  - repression (e.g. LacI, TetR, cI — Elowitz & Leibler 2000; Gardner et al. 2000)
  - activation (e.g. AraC-family activators — standard Hill activation form,
    see Alon, "An Introduction to Systems Biology", ch. 2)

WHAT IS UNBOUNDED:
- How many gene instances you create (name them anything)
- How those instances are wired together (any directed graph — rings,
  toggles, feed-forward loops, fan-in, fan-out, disconnected sub-circuits,
  anything)
- Multiple regulators on the same target gene (combined multiplicatively,
  the standard independent-binding-site approximation)

This is the same design principle Cello uses via its UCF files: a small,
characterized part-type library, an unbounded space of circuits built from it.
"""

from dataclasses import dataclass
from typing import Literal

EdgeType = Literal["repress", "activate"]

# Literature-typical Hill-function constants. These are starting points,
# not measured values for a specific named gene — treat per-instance
# overrides as "we're testing a different published parameter regime",
# never as invented biology.
MECHANISM_DEFAULTS = {
    "repress": {"alpha": 200.0, "alpha0": 0.0, "n": 2.0, "beta": 5.0, "K": 1.0},
    "activate": {"alpha": 200.0, "alpha0": 0.0, "n": 2.0, "beta": 5.0, "K": 1.0},
}

WHITELISTED_MECHANISMS = {"repress", "activate"}


@dataclass
class PartInstance:
    id: str                    # any name you choose — this is the unbounded axis
    maxExpression: float = 200.0
    basalExpression: float = 0.0
    hillCoeff: float = 2.0
    degradationRate: float = 5.0
    halfMaxConst: float = 1.0  # K in the Hill function


@dataclass
class Edge:
    frm: str
    to: str
    type: EdgeType


def validate_model(model: dict) -> tuple[bool, str]:
    """
    Enforcement gate. Every AI-proposed edit must pass this before touching
    the simulator. Checks the two things that are actually non-negotiable:
    (1) every edge's mechanism type is whitelisted, (2) every edge references
    parts that exist. Does NOT restrict shape, count, or names — those are
    the unbounded axes by design.
    """
    if "parts" not in model or "edges" not in model:
        return False, "Model must have 'parts' and 'edges' keys."

    if not isinstance(model["parts"], list) or len(model["parts"]) == 0:
        return False, "Model must have at least one part."

    ids = set()
    for p in model["parts"]:
        if "id" not in p:
            return False, f"Part missing 'id': {p}"
        if p["id"] in ids:
            return False, f"Duplicate part id: {p['id']}"
        ids.add(p["id"])

    for e in model["edges"]:
        for key in ("from", "to", "type"):
            if key not in e:
                return False, f"Edge missing '{key}': {e}"
        if e["type"] not in WHITELISTED_MECHANISMS:
            return False, (
                f"Edge type '{e['type']}' is not a whitelisted mechanism. "
                f"Only {WHITELISTED_MECHANISMS} are permitted — "
                f"the AI cannot invent a new regulatory mechanism."
            )
        if e["from"] not in ids:
            return False, f"Edge references unknown source part '{e['from']}'"
        if e["to"] not in ids:
            return False, f"Edge references unknown target part '{e['to']}'"

    return True, "ok"


def default_repressilator_model() -> dict:
    """Elowitz & Leibler (2000) ring, expressed in the new graph schema."""
    return {
        "parts": [
            {"id": "lacI", "maxExpression": 200.0, "basalExpression": 0.0,
             "hillCoeff": 2.0, "degradationRate": 5.0, "halfMaxConst": 1.0},
            {"id": "tetR", "maxExpression": 200.0, "basalExpression": 0.0,
             "hillCoeff": 2.0, "degradationRate": 5.0, "halfMaxConst": 1.0},
            {"id": "cI", "maxExpression": 200.0, "basalExpression": 0.0,
             "hillCoeff": 2.0, "degradationRate": 5.0, "halfMaxConst": 1.0},
        ],
        "edges": [
            {"from": "lacI", "to": "tetR", "type": "repress"},
            {"from": "tetR", "to": "cI", "type": "repress"},
            {"from": "cI", "to": "lacI", "type": "repress"},
        ],
    }


def default_toggle_model() -> dict:
    """Gardner, Cantor, Collins (2000) toggle, in the new graph schema."""
    return {
        "parts": [
            {"id": "geneU", "maxExpression": 3.0, "basalExpression": 0.0,
             "hillCoeff": 3.0, "degradationRate": 1.0, "halfMaxConst": 1.0},
            {"id": "geneV", "maxExpression": 3.0, "basalExpression": 0.0,
             "hillCoeff": 3.0, "degradationRate": 1.0, "halfMaxConst": 1.0},
        ],
        "edges": [
            {"from": "geneU", "to": "geneV", "type": "repress"},
            {"from": "geneV", "to": "geneU", "type": "repress"},
        ],
    }


def incoherent_feedforward_loop_model() -> dict:
    """
    A real, published, third circuit type, different in SHAPE from either
    ring or toggle — proof the schema is not restricted to those two.
    Type-1 incoherent feed-forward loop (Mangan & Alon, 2003): X activates Z
    directly AND activates Y, which represses Z. Classic result: Z shows a
    pulse then returns toward baseline even though X stays on — a shape
    neither the ring nor the toggle can produce.
    """
    return {
        "parts": [
            {"id": "geneX", "maxExpression": 100.0, "basalExpression": 5.0,
             "hillCoeff": 2.0, "degradationRate": 2.0, "halfMaxConst": 1.0},
            {"id": "geneY", "maxExpression": 100.0, "basalExpression": 0.0,
             "hillCoeff": 2.0, "degradationRate": 2.0, "halfMaxConst": 1.0},
            {"id": "geneZ", "maxExpression": 100.0, "basalExpression": 0.0,
             "hillCoeff": 2.0, "degradationRate": 2.0, "halfMaxConst": 1.0},
        ],
        "edges": [
            {"from": "geneX", "to": "geneY", "type": "activate"},
            {"from": "geneX", "to": "geneZ", "type": "activate"},
            {"from": "geneY", "to": "geneZ", "type": "repress"},
        ],
    }