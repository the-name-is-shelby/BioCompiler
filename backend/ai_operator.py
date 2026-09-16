"""
The AI layer. This is the only file in the whole project where an AI model
is called. It is deliberately restricted to two functions and nothing else:

  1. edit_circuit()   — takes an instruction + current model, returns an
                         EDITED MODEL JSON. Nothing else. Never a number,
                         never a biological claim in prose.
  2. explain_diff()    — takes a structured numeric diff (computed by the
                         real solver, in simulator.py) and returns English
                         explaining it. It never sees raw traces, and it
                         never sees the ability to invent a result — the
                         diff dict is the only information source it has.

If Gemini's edit fails whitelist validation, we reject it and raise —
we do NOT silently retry with a "fixed" version, because that would let
the AI eventually stumble onto something that shouldn't exist. Fail loud.
"""

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

from parts_library import validate_model

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

OPERATOR_SYSTEM_PROMPT = """You are a circuit-editing function, not a conversational assistant.

You will be given the CURRENT circuit model as JSON (a "parts" list and an
"edges" list) and a natural-language INSTRUCTION.

Return ONLY raw JSON with exactly two top-level keys: "model" and "substitution_note".

- "model": the complete edited model (the full "parts" and "edges" structure)
  after applying the instruction.
- "substitution_note": null if the instruction was fulfilled exactly as asked.
  If the instruction requested any mechanism, behavior, or biology that is
  NOT one of "repress" or "activate" (e.g. phosphorylation, degradation
  tagging, fluorescence, binding, anything else), you MUST NOT invent a new
  edge type for it. Instead substitute the closest whitelisted mechanism
  ("repress" or "activate") and set "substitution_note" to a short, honest
  string stating exactly what was requested and what was substituted instead
  — e.g. "Requested 'phosphorylate' is not a supported mechanism; substituted
  'activate' as the closest whitelisted analog." This note will be shown to
  the user and used by a second AI to write the explanation, so it must be
  accurate — never omit a substitution, and never describe it as anything
  other than what it literally is.

Non-negotiable rules:
- Every edge's "type" field must be exactly "repress" or "activate". No
  other mechanism exists in this system, ever, under any circumstance.
- Every part must have a unique string "id".
- You may add or remove parts and edges as needed to fulfil the instruction.
- If a new part is needed and the instruction doesn't specify its kinetic
  constants (maxExpression, basalExpression, hillCoeff, degradationRate,
  halfMaxConst), copy those values from an existing part already in the
  model rather than inventing new numbers.
- Every edge's "from" and "to" must reference a part id that exists in
  your returned "parts" list.
- If the instruction is ambiguous, make the single most literal reasonable
  interpretation and return a valid model — do not ask a clarifying
  question, you have no ability to ask one.
"""

EXPLAINER_SYSTEM_PROMPT = """You explain simulation results. You will be given the user's
original instruction, an optional substitution note, and a structured
numeric summary (final/max/min/mean values per gene, before the edit and
after it) computed by a real ODE solver. You have NOT seen the raw traces.

If a substitution note is present, your explanation MUST open by stating
plainly, in one sentence, what was requested and what was substituted
instead — using the substitution note's own wording, not softer language.
Never describe the substituted mechanism as if it were the originally
requested one.

Then, in 2-4 more plain-English sentences, explain what changed and why it
makes biological sense given what was ACTUALLY done (per the substitution
note if present, otherwise per the instruction). Reference only numbers
present in the summary you were given. Never state a number that isn't in
the data. Never describe a mechanism that isn't a simple consequence of one
gene repressing or activating another.

Write in plain sentences only. Do not use markdown formatting of any
kind — no asterisks, no underscores, no headers, no bullet points. This
text is displayed directly on a webpage with no markdown rendering.
"""


def edit_circuit(instruction: str, current_model: dict) -> tuple[dict, str | None]:
    """Returns (edited_model, substitution_note). substitution_note is None
    if the instruction was fulfilled exactly with no mechanism substitution."""
    ok, msg = validate_model(current_model)
    if not ok:
        raise ValueError(f"Current model is already invalid, refusing to edit: {msg}")

    prompt = f"Current model:\n{json.dumps(current_model)}\n\nInstruction: {instruction}"
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=OPERATOR_SYSTEM_PROMPT,
            response_mime_type="application/json",
        ),
    )

    try:
        parsed = json.loads(response.text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini did not return valid JSON: {e}. Raw output: {response.text[:500]}")

    if "model" not in parsed:
        raise ValueError(f"Gemini's response is missing the 'model' key: {response.text[:500]}")

    edited = parsed["model"]
    substitution_note = parsed.get("substitution_note")

    ok, msg = validate_model(edited)
    if not ok:
        raise ValueError(f"Gemini's proposed edit was REJECTED by the whitelist: {msg}")

    return edited, substitution_note


def explain_diff(instruction: str, diff_summary: dict, substitution_note: str | None = None) -> str:
    note_block = f"\n\nSubstitution note: {substitution_note}" if substitution_note else ""
    prompt = (
        f"User instruction: {instruction}{note_block}\n\n"
        f"Numeric diff (before vs after):\n{json.dumps(diff_summary)}"
    )
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=EXPLAINER_SYSTEM_PROMPT),
    )
    return response.text

EXPLAIN_CIRCUIT_SYSTEM_PROMPT = """You describe a simulated gene circuit's behavior in plain
English. You will be given the circuit's structure (which genes repress or activate which
others) and a per-gene numeric summary computed by a real solver: final value, max, min, mean,
and whether that gene's trace had settled to a steady value by the end of the simulation window
(true) or was still fluctuating substantially (false — this indicates oscillation or an
unfinished transient, not an error).

In 3-5 plain sentences, describe what the circuit does qualitatively — settles to a fixed state,
oscillates, one gene suppresses another toward zero, etc. — referencing only the genes and
numbers given. Never state a number not present in the data. Never invent kinetic detail beyond
what a repress/activate relationship implies.

Write in plain sentences only, no markdown."""


def explain_circuit(model: dict, characterization: dict) -> str:
    prompt = (
        f"Circuit structure:\n{json.dumps({'parts': [p['id'] for p in model['parts']], 'edges': model['edges']})}\n\n"
        f"Per-gene numeric summary:\n{json.dumps(characterization)}"
    )
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=EXPLAIN_CIRCUIT_SYSTEM_PROMPT),
    )
    return response.text

# ---------------------------------------------------------------------------
# Multi-agent review. Two specialists look at the SAME real solver output
# from two different lenses, independently (neither sees the other's text),
# then a third agent (Arbiter) synthesizes both into one final verdict.
# Every agent only ever sees real computed numbers or the real model JSON —
# never asked to invent a fact about the circuit.
# ---------------------------------------------------------------------------

AGENT_PHYSIOLOGIST_SYSTEM_PROMPT = """You are the CIRCUIT PHYSIOLOGIST, one of two specialist reviewers
analyzing a simulated gene circuit. Your lens is system-dynamics behavior only: whether the
circuit settles or oscillates, and what the stability classification implies for the circuit's
real-world reliability.

You will be given the circuit's structure and a real numeric summary from an ODE solver:
per-gene final/max/min/mean values, whether each species settled, and a stability classification
(equilibrium found or not; if found, stable/unstable/marginal with its eigenvalue). You have not
seen raw traces or the circuit's raw kinetic parameters — that is the other agent's job.

In 2-4 plain sentences, give your independent verdict: is the observed dynamic behavior consistent
with what the circuit's wiring suggests it should do, and what dynamics-specific risk (if any)
would you flag. Reference only numbers given to you. Never invent a number. Do not comment on
parameter values or biological plausibility — that is the other agent's job.

Write in plain sentences only, no markdown."""

AGENT_ARCHITECT_SYSTEM_PROMPT = """You are the CIRCUIT ARCHITECT, one of two specialist reviewers analyzing
a simulated gene circuit. Your lens is the circuit's own kinetic parameters only: each gene's
maxExpression, basalExpression, hillCoeff, degradationRate and halfMaxConst, as given directly in
the model. You are comparing genes within this SAME circuit against each other to flag any
parameter that stands out as an outlier relative to the rest of the circuit, and reasoning about
what that outlier would predict for behavior (e.g. a much slower degradation rate than its
neighbors makes a gene the slow node in the loop; a much higher Hill coefficient makes its
response sharper/more switch-like than the others). You have not seen the solver's stability
verdict or trace summary — that is the other agent's job.

In 2-4 plain sentences, give your independent verdict: are the parameters internally consistent
for this circuit's apparent purpose, and what design-specific risk (if any) would you flag.
Reference only the parameter values given to you. Never invent a number or a value you were not
given. Do not comment on the observed stability or trace outcome — that is the other agent's job.

Write in plain sentences only, no markdown."""

AGENT_ARBITER_SYSTEM_PROMPT = """You are the ARBITER. Two specialists — a Physiologist
and an Architect — have each independently reviewed the same circuit from different angles and
have NOT seen each other's text. You are given both of their written assessments, plus the same
real numeric summary the Physiologist saw.

In 3-5 plain sentences, produce ONE final verdict: state plainly whether the two assessments agree
or point in the same direction. If they raise different or conflicting concerns, say so explicitly,
state which one is the higher-priority risk and why, then give the single combined recommendation
a user should act on. Reference only facts and numbers present in what you were given — you have
no independent access to the circuit. Never invent a number.

Write in plain sentences only, no markdown."""


def agent_physiologist_review(model: dict, characterization: dict, stability: dict) -> str:
    payload = {
        "structure": {"parts": [p["id"] for p in model["parts"]], "edges": model["edges"]},
        "characterization": characterization,
        "stability": stability,
    }
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=json.dumps(payload),
        config=types.GenerateContentConfig(system_instruction=AGENT_PHYSIOLOGIST_SYSTEM_PROMPT),
    )
    return response.text


def agent_architect_review(model: dict) -> str:
    params = [
        {
            "id": p["id"],
            "maxExpression": p.get("maxExpression"),
            "basalExpression": p.get("basalExpression"),
            "hillCoeff": p.get("hillCoeff"),
            "degradationRate": p.get("degradationRate"),
            "halfMaxConst": p.get("halfMaxConst"),
        }
        for p in model["parts"]
    ]
    payload = {"structure": {"edges": model["edges"]}, "parameters": params}
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=json.dumps(payload),
        config=types.GenerateContentConfig(system_instruction=AGENT_ARCHITECT_SYSTEM_PROMPT),
    )
    return response.text


def agent_arbiter_verdict(physiologist_review: str, architect_review: str, characterization: dict) -> str:
    payload = {
        "physiologist_review": physiologist_review,
        "architect_review": architect_review,
        "numeric_summary": characterization,
    }
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=json.dumps(payload),
        config=types.GenerateContentConfig(system_instruction=AGENT_ARBITER_SYSTEM_PROMPT),
    )
    return response.text