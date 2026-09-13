"""
BioCompiler parts library — graph-general core, plus real characterized data.

A circuit is a list of gene instances (any number, any names) and a list of
directed regulatory edges between them, each either "repress" or "activate".

WHAT IS BOUNDED (on purpose, non-negotiable):
Only two regulatory MECHANISM TYPES are whitelisted, because only these two
have well-established, published Hill-function kinetic forms:
  - repression (e.g. LacI, TetR, cI — Elowitz & Leibler 2000; Gardner et al. 2000)
  - activation (standard Hill activation form, see Alon, "An Introduction to
    Systems Biology", ch. 2)

WHAT IS UNBOUNDED:
- How many gene instances you create (name them anything)
- How those instances are wired together (any directed graph)
- Multiple regulators on the same target gene (combined multiplicatively)
"""

from dataclasses import dataclass
from typing import Literal

EdgeType = Literal["repress", "activate"]

MECHANISM_DEFAULTS = {
    "repress": {"alpha": 200.0, "alpha0": 0.0, "n": 2.0, "beta": 5.0, "K": 1.0},
    "activate": {"alpha": 200.0, "alpha0": 0.0, "n": 2.0, "beta": 5.0, "K": 1.0},
}

WHITELISTED_MECHANISMS = {"repress", "activate"}


@dataclass
class PartInstance:
    id: str
    maxExpression: float = 200.0
    basalExpression: float = 0.0
    hillCoeff: float = 2.0
    degradationRate: float = 5.0
    halfMaxConst: float = 1.0


@dataclass
class Edge:
    frm: str
    to: str
    type: EdgeType


def validate_model(model: dict) -> tuple[bool, str]:
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
    """Elowitz & Leibler (2000) ring."""
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
    """Gardner, Cantor, Collins (2000) toggle."""
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
    """Type-1 incoherent feed-forward loop (Mangan & Alon, 2003)."""
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


# ---------------------------------------------------------------------------
# REAL, PUBLISHED, MEASURED PART DATA — not literature-typical illustrative
# constants like the three defaults above, but actual fitted Hill-function
# parameters from a real characterization experiment.
#
# Source: Table 1, "Precision design of stable genetic circuits carried in
# highly-insulated E. coli genomic landing pads" (Kim, Zhang et al., 2020,
# Molecular Systems Biology, PMC7436927). Six TetR-family repressors, fitted
# to y = ymin + (ymax-ymin)/(1+(x/K)^n) — the identical functional form this
# simulator already uses, so these values require no change to the math.
#
# HONESTY NOTE: the paper characterizes each gate's STATIC transfer function
# (steady-state input->output), not its protein decay rate — there is no
# published degradationRate in this table. degradationRate below is a
# generic modeling default, not a sourced measurement; everything else
# (maxExpression, basalExpression, hillCoeff, halfMaxConst) is real,
# measured, and cited.
# ---------------------------------------------------------------------------
REAL_CHARACTERIZED_PARTS = {
    "phlF":  {"ymax": 5.12, "ymin": 0.01, "K": 0.15, "n": 2.4},
    "qacR":  {"ymax": 4.52, "ymin": 0.04, "K": 0.97, "n": 4.3},
    "amtR":  {"ymax": 2.08, "ymin": 0.03, "K": 0.15, "n": 1.7},
    "bm3R1": {"ymax": 0.65, "ymin": 0.01, "K": 0.40, "n": 2.7},
    "ameR":  {"ymax": 3.69, "ymin": 0.03, "K": 0.13, "n": 1.7},
    "betI":  {"ymax": 2.25, "ymin": 0.25, "K": 1.25, "n": 3.8},
}
REAL_PART_CITATION = (
    "Kim, Zhang et al. 2020, Mol Syst Biol, 'Precision design of stable "
    "genetic circuits carried in highly-insulated E. coli genomic landing "
    "pads', Table 1 (PMC7436927)."
)


def real_part_to_schema(gene_id: str, degradation_rate: float = 1.0) -> dict:
    """Convert a real characterized part's published constants into this
    system's part schema. Raises if gene_id isn't in REAL_CHARACTERIZED_PARTS
    — never silently falls back to a made-up number for a named real gene."""
    if gene_id not in REAL_CHARACTERIZED_PARTS:
        raise ValueError(
            f"'{gene_id}' is not in the real characterized part library. "
            f"Available: {list(REAL_CHARACTERIZED_PARTS.keys())}"
        )
    d = REAL_CHARACTERIZED_PARTS[gene_id]
    return {
        "id": gene_id,
        "maxExpression": d["ymax"] - d["ymin"],
        "basalExpression": d["ymin"],
        "hillCoeff": d["n"],
        "degradationRate": degradation_rate,
        "halfMaxConst": d["K"],
    }


def real_gate_ring_model() -> dict:
    """A 3-gene ring built ENTIRELY from real, published, measured repressor
    data (PhlF, BetI, AmtR) rather than illustrative textbook constants."""
    return {
        "parts": [
            real_part_to_schema("phlF"),
            real_part_to_schema("betI"),
            real_part_to_schema("amtR"),
        ],
        "edges": [
            {"from": "phlF", "to": "betI", "type": "repress"},
            {"from": "betI", "to": "amtR", "type": "repress"},
            {"from": "amtR", "to": "phlF", "type": "repress"},
        ],
    }

# ---------------------------------------------------------------------------
# CELLO UCF DATA, FULL REPO — every gate library in CIDARLAB/Cello-UCF
# (Zenodo DOI archive 10.5281/zenodo.4675719, v1.0), all 3 chassis Cello
# publishes characterized gates for. Same functional form as everything
# above (y = ymin + (ymax-ymin)/(1+(x/K)^n)), zero solver changes needed.
# Keyed [library][gate_name] because gate names are NOT unique across
# files — e.g. "P1_PhlF" exists in both Eco1C1G1T1 and Eco1C2G2T2 with
# genuinely different fitted numbers (different characterization runs).
# Flattening these into one dict would silently overwrite real
# measurements with other real measurements.
#
# EXCLUDED ON PURPOSE: 12 entries from SC1C1G1T1 (yeast) whose parameters
# were ymax=ymin=0.01, K=n=1.0 on every single one — a degenerate flat
# response, not a real fit. These are Cello's own placeholder markers for
# the uncharacterized half of a tandem-promoter construct. Shipping them
# as real data would be indistinguishable from inventing a number.
#
# HONESTY NOTE ON Bth1C1G1T1: this file names its 7 gates "Gate1"-"Gate7"
# and its "regulator" field is the anonymized code "M1"-"M7" — the actual
# transcription factor identity is not disclosed in this public file. The
# numbers are real and citable to this exact file; the biological identity
# behind them is not known from this source.
# ---------------------------------------------------------------------------
CELLO_UCF_LIBRARIES = {
    "Eco1C1G1T1": {
        "A1_AmtR": {"regulator": "AmtR", "ymax": 3.8, "ymin": 0.06, "K": 0.07, "n": 1.6},
        "B1_BM3R1": {"regulator": "BM3R1", "ymax": 0.5, "ymin": 0.004, "K": 0.04, "n": 3.4},
        "B2_BM3R1": {"regulator": "BM3R1", "ymax": 0.5, "ymin": 0.005, "K": 0.15, "n": 2.9},
        "B3_BM3R1": {"regulator": "BM3R1", "ymax": 0.8, "ymin": 0.01, "K": 0.26, "n": 3.4},
        "E1_BetI": {"regulator": "BetI", "ymax": 3.8, "ymin": 0.07, "K": 0.41, "n": 2.4},
        "F1_AmeR": {"regulator": "AmeR", "ymax": 3.8, "ymin": 0.2, "K": 0.09, "n": 1.4},
        "H1_HlyIIR": {"regulator": "HlyIIR", "ymax": 2.5, "ymin": 0.07, "K": 0.19, "n": 2.6},
        "I1_IcaRA": {"regulator": "IcaRA", "ymax": 2.2, "ymin": 0.08, "K": 0.1, "n": 1.4},
        "L1_LitR": {"regulator": "LitR", "ymax": 4.3, "ymin": 0.07, "K": 0.05, "n": 1.7},
        "N1_LmrA": {"regulator": "LmrA", "ymax": 2.2, "ymin": 0.2, "K": 0.18, "n": 2.1},
        "P1_PhlF": {"regulator": "PhlF", "ymax": 3.9, "ymin": 0.01, "K": 0.03, "n": 4.0},
        "P2_PhlF": {"regulator": "PhlF", "ymax": 4.1, "ymin": 0.02, "K": 0.13, "n": 3.9},
        "P3_PhlF": {"regulator": "PhlF", "ymax": 6.8, "ymin": 0.02, "K": 0.23, "n": 4.2},
        "Q1_QacR": {"regulator": "QacR", "ymax": 2.4, "ymin": 0.01, "K": 0.05, "n": 2.7},
        "Q2_QacR": {"regulator": "QacR", "ymax": 2.8, "ymin": 0.03, "K": 0.21, "n": 2.4},
        "R1_PsrA": {"regulator": "PsrA", "ymax": 5.9, "ymin": 0.2, "K": 0.19, "n": 1.8},
        "S1_SrpR": {"regulator": "SrpR", "ymax": 1.3, "ymin": 0.003, "K": 0.01, "n": 2.9},
        "S2_SrpR": {"regulator": "SrpR", "ymax": 2.1, "ymin": 0.003, "K": 0.04, "n": 2.6},
        "S3_SrpR": {"regulator": "SrpR", "ymax": 2.1, "ymin": 0.004, "K": 0.06, "n": 2.8},
        "S4_SrpR": {"regulator": "SrpR", "ymax": 2.1, "ymin": 0.007, "K": 0.1, "n": 2.8},
    },
    "Eco1C2G2T2": {
        "A1_AmtR": {"regulator": "AmtR", "ymax": 3.13661101, "ymin": 0.035221608, "K": 0.047427884, "n": 1.656171138},
        "B1_BM3R1": {"regulator": "BM3R1", "ymax": 0.577806096, "ymin": 0.003721745, "K": 0.055519757, "n": 2.888263374},
        "B2_BM3R1": {"regulator": "BM3R1", "ymax": 0.486313131, "ymin": 0.005549518, "K": 0.574115383, "n": 3.842787839},
        "B3_BM3R1": {"regulator": "BM3R1", "ymax": 0.584759421, "ymin": 0.004958926, "K": 0.211950504, "n": 3.085977286},
        "C1_CymR": {"regulator": "CymR", "ymax": 3.004170775, "ymin": 0.00978549, "K": 0.100908709, "n": 3.693304378},
        "E1_BetI": {"regulator": "BetI", "ymax": 2.837857442, "ymin": 0.040842627, "K": 0.277844523, "n": 2.880416695},
        "F1_AmeR": {"regulator": "AmeR", "ymax": 4.566156271, "ymin": 0.289281104, "K": 0.121548379, "n": 1.542139516},
        "F2_AmeR": {"regulator": "AmeR", "ymax": 3.674478971, "ymin": 0.206243141, "K": 0.0346134, "n": 1.314222122},
        "H1_HlyIIR": {"regulator": "HlyIIR", "ymax": 2.056076677, "ymin": 0.004353486, "K": 0.130693758, "n": 2.588160165},
        "N1_LmrA": {"regulator": "LmrA", "ymax": 1.265439, "ymin": 0.077273193, "K": 0.093521178, "n": 1.754564179},
        "P1_PhlF": {"regulator": "PhlF", "ymax": 6.873413202, "ymin": 0.004337295, "K": 0.042126721, "n": 3.804263913},
        "P2_PhlF": {"regulator": "PhlF", "ymax": 7.486865464, "ymin": 0.006679767, "K": 0.20384996, "n": 4.481560106},
        "P3_PhlF": {"regulator": "PhlF", "ymax": 7.088098911, "ymin": 0.004656815, "K": 0.116044457, "n": 3.342819362},
        "S1_SrpR": {"regulator": "SrpR", "ymax": 1.366504087, "ymin": 0.00135452, "K": 0.016906016, "n": 3.095316853},
        "S2_SrpR": {"regulator": "SrpR", "ymax": 3.1684454, "ymin": 0.002829301, "K": 0.062531512, "n": 2.655303675},
        "S3_SrpR": {"regulator": "SrpR", "ymax": 3.055531711, "ymin": 0.00405468, "K": 0.087385601, "n": 2.657349101},
        "S4_SrpR": {"regulator": "SrpR", "ymax": 3.165985717, "ymin": 0.004347046, "K": 0.110327837, "n": 2.654076554},
        "V1_VanR": {"regulator": "VanR", "ymax": 6.174441542, "ymin": 0.043503414, "K": 0.049692514, "n": 2.984652678},
    },
    "Eco1C1G1T0": {
        "A1_AmtR": {"regulator": "AmtR", "ymax": 3.8, "ymin": 0.06, "K": 0.07, "n": 1.6},
        "B1_BM3R1": {"regulator": "BM3R1", "ymax": 0.5, "ymin": 0.004, "K": 0.04, "n": 3.4},
        "B2_BM3R1": {"regulator": "BM3R1", "ymax": 0.5, "ymin": 0.005, "K": 0.15, "n": 2.9},
        "B3_BM3R1": {"regulator": "BM3R1", "ymax": 0.8, "ymin": 0.01, "K": 0.26, "n": 3.4},
        "E1_BetI": {"regulator": "BetI", "ymax": 3.8, "ymin": 0.07, "K": 0.41, "n": 2.4},
        "F1_AmeR": {"regulator": "AmeR", "ymax": 3.8, "ymin": 0.2, "K": 0.09, "n": 1.4},
        "H1_HlyIIR": {"regulator": "HlyIIR", "ymax": 2.5, "ymin": 0.07, "K": 0.19, "n": 2.6},
        "P1_PhlF": {"regulator": "PhlF", "ymax": 3.9, "ymin": 0.01, "K": 0.03, "n": 4.0},
        "P2_PhlF": {"regulator": "PhlF", "ymax": 4.1, "ymin": 0.02, "K": 0.13, "n": 3.9},
        "P3_PhlF": {"regulator": "PhlF", "ymax": 6.8, "ymin": 0.02, "K": 0.23, "n": 4.2},
        "S1_SrpR": {"regulator": "SrpR", "ymax": 1.3, "ymin": 0.003, "K": 0.01, "n": 2.9},
        "S2_SrpR": {"regulator": "SrpR", "ymax": 2.1, "ymin": 0.003, "K": 0.04, "n": 2.6},
        "S3_SrpR": {"regulator": "SrpR", "ymax": 2.1, "ymin": 0.004, "K": 0.06, "n": 2.8},
        "S4_SrpR": {"regulator": "SrpR", "ymax": 2.1, "ymin": 0.007, "K": 0.1, "n": 2.8},
    },
    "Eco2C1G3T1": {
        "A1_AmtR_a": {"regulator": "AmtR_a", "ymax": 2.078139, "ymin": 0.02532, "K": 0.147489, "n": 1.698},
        "A1_AmtR_b": {"regulator": "AmtR_b", "ymax": 2.078139, "ymin": 0.02532, "K": 0.147489, "n": 1.698},
        "B3_BM3R1_a": {"regulator": "BM3R1_a", "ymax": 0.647559, "ymin": 0.00633, "K": 0.39879, "n": 2.7117},
        "B3_BM3R1_b": {"regulator": "BM3R1_b", "ymax": 0.647559, "ymin": 0.00633, "K": 0.39879, "n": 2.7117},
        "E1_BetI_a": {"regulator": "BetI_a", "ymax": 2.249049, "ymin": 0.2532, "K": 1.250808, "n": 3.776},
        "E1_BetI_b": {"regulator": "BetI_b", "ymax": 2.249049, "ymin": 0.2532, "K": 1.250808, "n": 3.776},
        "F2_AmeRs_a": {"regulator": "AmeRs_a", "ymax": 3.694188, "ymin": 0.03165, "K": 0.127233, "n": 1.7396},
        "F2_AmeRs_b": {"regulator": "AmeRs_b", "ymax": 3.694188, "ymin": 0.03165, "K": 0.127233, "n": 1.7396},
        "P1_PhlF_a": {"regulator": "PhlF_a", "ymax": 5.120337, "ymin": 0.008229, "K": 0.15192, "n": 2.4223},
        "P1_PhlF_b": {"regulator": "PhlF_b", "ymax": 5.120337, "ymin": 0.008229, "K": 0.15192, "n": 2.4223},
        "Q1_QacR_a": {"regulator": "QacR_a", "ymax": 4.518354, "ymin": 0.03798, "K": 0.970389, "n": 4.3237},
        "Q1_QacR_b": {"regulator": "QacR_b", "ymax": 4.518354, "ymin": 0.03798, "K": 0.970389, "n": 4.3237},
        "R1_PsrA_a": {"regulator": "PsrA_a", "ymax": 4.46898, "ymin": 0.9495, "K": 1.017864, "n": 2.8455},
        "R1_PsrA_b": {"regulator": "PsrA_b", "ymax": 4.46898, "ymin": 0.9495, "K": 1.017864, "n": 2.8455},
    },
    "Bth1C1G1T1": {
        "Gate1": {"regulator": "M1", "ymax": 0.7046, "ymin": 0.001, "K": 0.1925, "n": 1.259},
        "Gate2": {"regulator": "M2", "ymax": 0.08645, "ymin": 0.001, "K": 0.1143, "n": 1.257},
        "Gate3": {"regulator": "M3", "ymax": 0.3622, "ymin": 0.001, "K": 0.1327, "n": 1.311},
        "Gate4": {"regulator": "M4", "ymax": 0.1504, "ymin": 0.001, "K": 0.082, "n": 1.145},
        "Gate5": {"regulator": "M5", "ymax": 0.3382, "ymin": 0.001, "K": 0.09913, "n": 1.254},
        "Gate6": {"regulator": "M6", "ymax": 0.1291, "ymin": 0.001, "K": 0.09522, "n": 1.207},
        "Gate7": {"regulator": "M7", "ymax": 0.1553, "ymin": 0.001, "K": 0.2858, "n": 1.164},
    },
    "SC1C1G1T1": {
        "P1_BM3RI_a": {"regulator": "BM3RI_a", "ymax": 5.07, "ymin": 0.004, "K": 0.134, "n": 3.15},
        "P1_CI434_a": {"regulator": "CI434_a", "ymax": 3.57, "ymin": 0.02, "K": 0.283, "n": 3.86},
        "P1_CI_a": {"regulator": "CI_a", "ymax": 2.25, "ymin": 0.015, "K": 0.0705, "n": 2.06},
        "P1_HKCI_a": {"regulator": "HKCI_a", "ymax": 2.18, "ymin": 0.02, "K": 0.222, "n": 2.97},
        "P1_IcaR_a": {"regulator": "IcaR_a", "ymax": 2.65, "ymin": 0.003, "K": 0.136, "n": 2.72},
        "P1_LexA_a": {"regulator": "LexA_a", "ymax": 1.46, "ymin": 0.002, "K": 0.123, "n": 2.94},
        "P1_PhlF_a": {"regulator": "PhlF_a", "ymax": 3.21, "ymin": 0.006, "K": 0.211, "n": 3.57},
        "P1_PsrA_a": {"regulator": "PsrA_a", "ymax": 2.62, "ymin": 0.012, "K": 0.355, "n": 4.46},
        "P1_QacR_a": {"regulator": "QacR_a", "ymax": 2.24, "ymin": 0.002, "K": 0.19, "n": 3.36},
        "P2_CI434_a": {"regulator": "CI434_a", "ymax": 2.22, "ymin": 0.016, "K": 0.303, "n": 3.92},
        "P2_CI_a": {"regulator": "CI_a", "ymax": 3.82, "ymin": 0.02, "K": 0.164, "n": 3.08},
        "P2_LexA_a": {"regulator": "LexA_a", "ymax": 2.23, "ymin": 0.011, "K": 0.286, "n": 3.82},
    },
}
CELLO_UCF_CITATION = (
    "CIDARLAB/Cello-UCF, Zenodo DOI 10.5281/zenodo.4675719 (v1.0) - the "
    "gate libraries shipped with Cello 2.0 (Nielsen et al. 2016, Science). "
    "Bth1C1G1T1 discloses gate numbers but not regulator identity (see note above)."
)


def cello_gate_to_schema(library: str, gate_id: str, degradation_rate: float = 1.0) -> dict:
    """Convert a real Cello UCF gate's published constants into this
    system's part schema. Requires BOTH library and gate_id since gate
    names collide across libraries with different real numbers. Raises on
    any unknown library or gate — never invents a number for either."""
    if library not in CELLO_UCF_LIBRARIES:
        raise ValueError(
            f"'{library}' is not a known Cello UCF library. "
            f"Available: {list(CELLO_UCF_LIBRARIES.keys())}"
        )
    if gate_id not in CELLO_UCF_LIBRARIES[library]:
        raise ValueError(
            f"'{gate_id}' is not in library '{library}'. "
            f"Available: {list(CELLO_UCF_LIBRARIES[library].keys())}"
        )
    d = CELLO_UCF_LIBRARIES[library][gate_id]
    return {
        "id": f"{library}_{gate_id}",
        "maxExpression": d["ymax"] - d["ymin"],
        "basalExpression": d["ymin"],
        "hillCoeff": d["n"],
        "degradationRate": degradation_rate,
        "halfMaxConst": d["K"],
    }

def cello_nor_gate_demo() -> dict:
    """Two independent, real Cello-characterized repressor gates (SrpR and
    PhlF variants, both from the Eco1C1G1T1 library) both wired to repress
    a shared output — a genuine 2-input NOR topology."""
    return {
        "parts": [
            cello_gate_to_schema("Eco1C1G1T1", "S1_SrpR"),
            cello_gate_to_schema("Eco1C1G1T1", "P1_PhlF"),
            {"id": "output", "maxExpression": 100.0, "basalExpression": 0.0,
             "hillCoeff": 2.0, "degradationRate": 2.0, "halfMaxConst": 1.0},
        ],
        "edges": [
            {"from": "Eco1C1G1T1_S1_SrpR", "to": "output", "type": "repress"},
            {"from": "Eco1C1G1T1_P1_PhlF", "to": "output", "type": "repress"},
        ],
    }