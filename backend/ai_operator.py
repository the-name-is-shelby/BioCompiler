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