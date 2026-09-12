"""
BioCompiler simulator, v2 — graph-general.

Builds the ODE system directly from whatever parts+edges are in the model,
with no assumption about shape. A gene can have zero, one, or many
regulators of either type; multiple regulators combine multiplicatively
(the standard independent-binding-site approximation used throughout
synthetic biology modeling — see Alon, ch. 2).

    d(mRNA_i)/dt   = -mRNA_i + alpha_i * A_i(t) * R_i(t) + alpha0_i
    d(protein_i)/dt = -beta_i * (protein_i - mRNA_i)

where, for gene i with activator inputs a in Act_i and repressor inputs
r in Rep_i (all protein levels, K = half-max constant, n = Hill coeff):

    A_i(t) = 1                                   if Act_i is empty
             product over a of  a^n / (K^n + a^n) otherwise
    R_i(t) = 1                                   if Rep_i is empty
             product over r of  1 / (1 + (r/K)^n) otherwise

This is the sole source of numeric truth. The AI never touches this file
or its output — it only ever supplies model JSON in, and reads back a
structured diff, never raw numbers it could alter.
"""

import numpy as np
from scipy.integrate import solve_ivp

from parts_library import validate_model


def simulate(model: dict, t_span=(0, 200), n_points=2000, initial_perturbation=1.0) -> dict:
    """
    Simulate ANY valid graph — ring, toggle, feed-forward loop, fan-out,
    disconnected components, whatever the model describes. No topology
    parameter because none is needed.
    """
    ok, msg = validate_model(model)
    if not ok:
        raise ValueError(f"Invalid model, refusing to simulate: {msg}")

    parts = {p["id"]: p for p in model["parts"]}
    ids = list(parts.keys())
    n_genes = len(ids)
    idx = {gid: i for i, gid in enumerate(ids)}

    activators_of = {gid: [] for gid in ids}
    repressors_of = {gid: [] for gid in ids}
    for e in model["edges"]:
        if e["type"] == "activate":
            activators_of[e["to"]].append(e["from"])
        else:
            repressors_of[e["to"]].append(e["from"])

    alpha = np.array([parts[g].get("maxExpression", 200.0) for g in ids])
    alpha0 = np.array([parts[g].get("basalExpression", 0.0) for g in ids])
    n_hill = np.array([parts[g].get("hillCoeff", 2.0) for g in ids])
    beta = np.array([parts[g].get("degradationRate", 5.0) for g in ids])
    K = np.array([parts[g].get("halfMaxConst", 1.0) for g in ids])

    def odes(t, y):
        mrna = y[0:n_genes]
        protein = y[n_genes:2 * n_genes]
        dmrna = np.zeros(n_genes)
        dprotein = np.zeros(n_genes)
        for gid in ids:
            i = idx[gid]
            A = 1.0
            for a_id in activators_of[gid]:
                a_level = protein[idx[a_id]]
                A *= (a_level ** n_hill[i]) / (K[i] ** n_hill[i] + a_level ** n_hill[i] + 1e-12)
            R = 1.0
            for r_id in repressors_of[gid]:
                r_level = protein[idx[r_id]]
                R *= 1.0 / (1.0 + (r_level / K[i]) ** n_hill[i])
            dmrna[i] = -mrna[i] + alpha[i] * A * R + alpha0[i]
            dprotein[i] = -beta[i] * (protein[i] - mrna[i])
        return np.concatenate([dmrna, dprotein])

    y0 = np.zeros(2 * n_genes)
    y0[0] = initial_perturbation  # symmetry-breaking nudge

    t_eval = np.linspace(*t_span, n_points)
    sol = solve_ivp(odes, t_span, y0, t_eval=t_eval, method="LSODA", rtol=1e-6, atol=1e-9)

    species = {}
    for gid in ids:
        i = idx[gid]
        species[f"{gid}_mRNA"] = sol.y[i].tolist()
        species[f"{gid}_protein"] = sol.y[n_genes + i].tolist()

    return {"t": sol.t.tolist(), "species": species, "success": bool(sol.success)}


def diff_traces(before: dict, after: dict) -> dict:
    """Structured numeric diff — the only thing the AI explainer ever reads."""
    summary = {}
    for run_name, run in (("before", before), ("after", after)):
        run_summary = {}
        for name, values in run["species"].items():
            arr = np.array(values)
            run_summary[name] = {
                "final_value": round(float(arr[-1]), 3),
                "max_value": round(float(arr.max()), 3),
                "min_value": round(float(arr.min()), 3),
                "mean_value": round(float(arr.mean()), 3),
            }
        summary[run_name] = run_summary
    return summary