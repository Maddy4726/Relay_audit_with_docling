"""Prompts for semantic section segmentation (relay test reports only)."""

from __future__ import annotations

SECTION_SYSTEM_PROMPT = """You are a specialist in industrial relay protection and commissioning reports.

Your ONLY task is semantic section segmentation: decide which contiguous line span belongs to which technical section of the report.

You MUST:
- Use the provided bracketed line numbers (e.g. [0120]) as authoritative global indices when you set start_line and end_line.
- Infer section_type using semantic meaning, not literal heading matches. Headings are inconsistent across vendors.
- Map synonymous or abbreviated headings to the canonical section_type values listed below.
- Return detections that cover the numbered excerpt you were given. If a section clearly continues past the excerpt, still clip end_line to lines you can see.
- Output JSON ONLY. No markdown fences, no commentary, no keys other than the required wrapper.

Canonical section_type values (extend only if absolutely necessary):
- contact_resistance — contact resistance / CRM / static contact / millivolt drop style blocks
- insulation_resistance — megger / IR / insulation tests
- overload_protection — thermal / overload / heater / OL trip characterisation
- relay_timing — pickup/dropout, operate time, timing diagrams, characteristic tests
- ct_polarity — CT ratio, polarity, burden, knee-point, excitation curves

Semantic matching examples (non-exhaustive):
- "CRM TEST", "CONTACT RES TEST", "STATIC CONTACT TEST", "CONTACT RESISTANCE" → contact_resistance
- "MEGGER TEST", "IR TEST", "INSULATION RESISTANCE" → insulation_resistance
- "OVERLOAD", "THERMAL TRIP", "HEATER TEST" → overload_protection
- "PICKUP", "DROPOUT", "OPERATE TIME", "TIME DIAL" → relay_timing
- "CT POLARITY", "RATIO TEST", "EXCITATION" → ct_polarity

You MUST NOT:
- extract numeric measurement values
- judge pass/fail or compliance
- summarise narrative
- validate schemas or tables
- invent line numbers outside the excerpt

Each detection must include realistic confidence in [0,1] based on how clearly the span matches the inferred section semantics.

Respond with JSON of the form:
{"sections":[{"section_type":"...","detected_title":"...","start_line":120,"end_line":148,"confidence":0.94}]}
"""


FEW_SHOT_USER_1 = """[0001] ABC RELAY SERVICES
[0002] JOB: 55421 — SEL-751 FEEDER
[0003]
[0004] CRM TEST — AS LEFT
[0005] Inject 10 A secondary; sense 32.4 mV
[0006] Repeat after tap change
[0007]
[0008] MEGGER — PHASE A TO GROUND
[0009] Applied 1 kV, 60 s dwell
[0010]"""

FEW_SHOT_ASSISTANT_1 = """{"sections":[{"section_type":"contact_resistance","detected_title":"CRM TEST — AS LEFT","start_line":4,"end_line":6,"confidence":0.9},{"section_type":"insulation_resistance","detected_title":"MEGGER — PHASE A TO GROUND","start_line":8,"end_line":9,"confidence":0.88}]}"""


FEW_SHOT_USER_2 = """[0200] CT RATIO / POLARITY
[0201] Primary inject 600 A; secondary 5.01 A
[0202] Polarity mark matches diagram Sheet 4
[0203]
[0204] TIME DIAL 3 — OPERATE TIME
[0205] Trip at 23.8 ms at nominal voltage"""

FEW_SHOT_ASSISTANT_2 = """{"sections":[{"section_type":"ct_polarity","detected_title":"CT RATIO / POLARITY","start_line":200,"end_line":202,"confidence":0.93},{"section_type":"relay_timing","detected_title":"TIME DIAL 3 — OPERATE TIME","start_line":204,"end_line":205,"confidence":0.86}]}"""


def build_user_prompt(numbered_chunk_text: str) -> str:
    """Create the user message for one numbered chunk."""
    return (
        "Numbered relay test report excerpt:\n\n"
        f"{numbered_chunk_text}\n\n"
        "Identify semantic sections. Return JSON using the wrapper {\"sections\": [...]} "
        "with objects containing section_type, detected_title, start_line, end_line, confidence."
    )
