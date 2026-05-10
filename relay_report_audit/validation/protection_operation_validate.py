"""
Deterministic engineering checks: protection trip tables vs normalized metadata.

No LLMs. Uses conservative tolerances suitable for field test reports.
"""

from __future__ import annotations

import re
from typing import Any, Final, Sequence

from relay_report_audit.schemas.protection_operation_validation import (
    ProtectionEngineeringCheck,
    ProtectionOperationValidationResult,
)

# --- Tolerances (engineering-safe defaults) ---
_DTOC_REL: Final[float] = 0.10
_DTOC_ABS_S: Final[float] = 0.06
_MICRO_DELAY_S: Final[float] = 0.001  # below this, skip strict delay match
_MICRO_DELAY_OP_MAX_S: Final[float] = 2.0  # operated time sanity upper bound

_THERMAL_REL: Final[float] = 0.05
_THERMAL_ABS_S: Final[float] = 0.25

_STARTUP_REL: Final[float] = 0.08
_STARTUP_ABS_S: Final[float] = 0.25

_STALL_UPPER_REL: Final[float] = 0.10
_STALL_UPPER_ABS_S: Final[float] = 0.50

_EARTH_REL: Final[float] = 0.12
_EARTH_ABS_S: Final[float] = 0.15

_MONO_REL: Final[float] = 0.05
_MONO_ABS_S: Final[float] = 0.02

_IEC_SI_ALPHA: Final[float] = 0.02  # documented for SI-style scatter check


def _parse_float_cell(cell: str) -> float | None:
    s = (cell or "").strip().replace(",", "")
    if not s or s.upper() in ("-", "N/A", "NA", "OPERATED"):
        return None
    if s.startswith(">") or s.startswith("<"):
        s = s[1:]
    try:
        return float(s)
    except ValueError:
        return None


def _headers_joined_upper(headers: Sequence[str]) -> str:
    return " ".join(h or "" for h in headers).upper()


def _is_reference_footer_table(headers: Sequence[str]) -> bool:
    if not headers:
        return True
    j = _headers_joined_upper(headers)
    return "REFERENCE" in j and "TESTED BY" in j


def _is_protection_trip_table(tab: dict[str, Any]) -> bool:
    headers = tab.get("headers") or []
    if _is_reference_footer_table(headers):
        return False
    j = _headers_joined_upper(headers)
    return "INJECT" in j and ("OPERATED" in j or "CALCULATED" in j)


def _iter_trip_tables(tables: Sequence[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not tables:
        return []
    return [t for t in tables if isinstance(t, dict) and _is_protection_trip_table(t)]


def _find_col_index(headers: Sequence[str], *needles: str) -> int | None:
    for i, h in enumerate(headers):
        u = (h or "").upper()
        if all(n in u for n in needles):
            return i
    return None


def _first_numeric_injected_operated_pair(tab: dict[str, Any]) -> tuple[int, float, float] | None:
    headers = list(tab.get("headers") or [])
    rows = tab.get("rows") or []
    i_inj = _find_col_index(headers, "INJECT")
    i_op = _find_col_index(headers, "OPERATED")
    if i_inj is None or i_op is None:
        return None
    for ri, row in enumerate(rows):
        if len(row) <= max(i_inj, i_op):
            continue
        inj = _parse_float_cell(row[i_inj])
        op = _parse_float_cell(row[i_op])
        if inj is not None and op is not None:
            return ri, inj, op
    return None


def _first_numeric_calc_operated_pair(tab: dict[str, Any]) -> tuple[int, float, float] | None:
    headers = list(tab.get("headers") or [])
    rows = tab.get("rows") or []
    i_calc = _find_col_index(headers, "CALCULATED")
    i_op = _find_col_index(headers, "OPERATED")
    if i_calc is None or i_op is None:
        return None
    for ri, row in enumerate(rows):
        if len(row) <= max(i_calc, i_op):
            continue
        c = _parse_float_cell(row[i_calc])
        op = _parse_float_cell(row[i_op])
        if c is not None and op is not None:
            return ri, c, op
    return None


def _extract_idmt_injected_operated_points(tab: dict[str, Any]) -> list[tuple[float, float]] | None:
    """Return (I, t_op) points in column order (X2, X4, X6) for grouped IDMT tables."""
    headers = list(tab.get("headers") or [])
    rows = list(tab.get("rows") or [])
    gh = tab.get("grouped_headers") or []
    n_sub = 0
    inj_start = 0
    if gh and len(gh) >= 2:
        cols0 = gh[0].get("columns") or []
        cols1 = gh[1].get("columns") or []
        if len(cols0) >= 2 and len(cols1) == len(cols0):
            n_sub = len(cols0)
            inj_start = 1
    inj_cols: list[int] = []
    op_cols: list[int] = []
    if n_sub > 0:
        inj_cols = [inj_start + j for j in range(n_sub)]
        op_cols = [inj_start + n_sub + j for j in range(n_sub)]
    else:
        for i, h in enumerate(headers):
            hu = (h or "").upper()
            if "INJECT" in hu and re.search(r"\bX[246]\b", hu):
                inj_cols.append(i)
            if "OPERATED" in hu and re.search(r"\bX[246]\b", hu):
                op_cols.append(i)
        if len(inj_cols) >= 3 and len(op_cols) >= 3:
            inj_cols = sorted(inj_cols)[:3]
            op_cols = sorted(op_cols)[:3]
            n_sub = 3
        else:
            return None

    for row in rows:
        if len(row) <= max(max(inj_cols, default=0), max(op_cols, default=0)):
            continue
        pts: list[tuple[float, float]] = []
        ok = True
        for ic, oc in zip(inj_cols, op_cols):
            vi = _parse_float_cell(row[ic] if ic < len(row) else "")
            vo = _parse_float_cell(row[oc] if oc < len(row) else "")
            if vi is None or vo is None:
                ok = False
                break
            pts.append((vi, vo))
        if ok and len(pts) >= 2:
            return pts
    return None


def _mono_epsilon(times: Sequence[float]) -> float:
    if not times:
        return _MONO_ABS_S
    return max(_MONO_ABS_S, _MONO_REL * max(abs(t) for t in times))


def _check_inverse_time_monotonicity(points: list[tuple[float, float]]) -> ProtectionEngineeringCheck:
    """Higher injected current => shorter or equal operated time (inverse-time trend)."""
    pts = sorted(points, key=lambda p: p[0])
    times = [p[1] for p in pts]
    currents = [p[0] for p in pts]
    eps = _mono_epsilon(times)
    violations: list[dict[str, Any]] = []
    for i in range(len(pts) - 1):
        if times[i] + eps < times[i + 1]:
            violations.append(
                {
                    "index_low": i,
                    "I_low": currents[i],
                    "t_low": times[i],
                    "I_high": currents[i + 1],
                    "t_high": times[i + 1],
                    "epsilon_seconds": eps,
                }
            )
    ev: dict[str, Any] = {
        "points_I_A": currents,
        "points_t_sec": times,
        "epsilon_seconds": eps,
        "iec_si_exponent_documented": _IEC_SI_ALPHA,
    }
    if violations:
        return ProtectionEngineeringCheck(
            type="inverse_time_monotonicity",
            status="FAIL",
            message="Operated time did not decrease (within tolerance) as injected current increased.",
            evidence={**ev, "violations": violations},
            tolerance={"mono_rel": _MONO_REL, "mono_abs_s": _MONO_ABS_S},
        )
    return ProtectionEngineeringCheck(
        type="inverse_time_monotonicity",
        status="PASS",
        message="Operated times are monotone non-increasing with increasing injection.",
        evidence=ev,
        tolerance={"mono_rel": _MONO_REL, "mono_abs_s": _MONO_ABS_S},
    )


def _check_dtoc_delay(
    *,
    delay_s: float,
    t_meas: float,
    raw_meta: str | None,
    row_index: int,
) -> ProtectionEngineeringCheck:
    tol = max(_DTOC_ABS_S, _DTOC_REL * max(delay_s, 1e-9))
    ev: dict[str, Any] = {
        "expected_delay_seconds": delay_s,
        "measured_operated_seconds": t_meas,
        "table_row_index": row_index,
        "raw_metadata_text": raw_meta,
    }
    if delay_s < _MICRO_DELAY_S:
        ok_sane = 0.0 < t_meas < _MICRO_DELAY_OP_MAX_S
        return ProtectionEngineeringCheck(
            type="dtoc_delay_consistency",
            status="PASS" if ok_sane else "WARN",
            message=(
                "Programmed delay is sub-millisecond; strict equality vs operated time is skipped. "
                "Sanity: operated time within a bounded window."
                if ok_sane
                else "Operated time outside expected sanity window for a micro-delay DTOC element."
            ),
            evidence={**ev, "comparison_mode": "micro_delay_sanity"},
            tolerance={"operated_max_s": _MICRO_DELAY_OP_MAX_S},
        )
    diff = abs(t_meas - delay_s)
    st = "PASS" if diff <= tol else "WARN" if diff <= tol * 1.5 else "FAIL"
    return ProtectionEngineeringCheck(
        type="dtoc_delay_consistency",
        status=st,  # type: ignore[arg-type]
        message=None if st == "PASS" else f"|measured - setting| = {diff:.4g}s vs tol {tol:.4g}s.",
        evidence={**ev, "absolute_difference_seconds": diff},
        tolerance={"relative": _DTOC_REL, "absolute_seconds": _DTOC_ABS_S},
    )


def _check_thermal_timing(t_calc: float, t_op: float, *, row_index: int) -> ProtectionEngineeringCheck:
    tol = max(_THERMAL_ABS_S, _THERMAL_REL * max(abs(t_calc), 1e-9))
    diff = abs(t_op - t_calc)
    st = "PASS" if diff <= tol else "WARN" if diff <= tol * 1.4 else "FAIL"
    return ProtectionEngineeringCheck(
        type="thermal_overload_timing_consistency",
        status=st,  # type: ignore[arg-type]
        message=None if st == "PASS" else f"|operated - calculated| = {diff:.4g}s vs tol {tol:.4g}s.",
        evidence={
            "calculated_time_seconds": t_calc,
            "operated_time_seconds": t_op,
            "table_row_index": row_index,
            "absolute_difference_seconds": diff,
        },
        tolerance={"relative": _THERMAL_REL, "absolute_seconds": _THERMAL_ABS_S},
    )


def _check_startup_timing(limit_s: float, t_op: float, *, row_index: int) -> ProtectionEngineeringCheck:
    bound = limit_s * (1.0 + _STARTUP_REL) + _STARTUP_ABS_S
    st = "PASS" if t_op <= bound else "FAIL"
    return ProtectionEngineeringCheck(
        type="startup_supervision_timing_consistency",
        status=st,  # type: ignore[arg-type]
        message=None if st == "PASS" else f"Operated time {t_op:.4g}s exceeds limit+tol ({bound:.4g}s).",
        evidence={
            "startup_time_limit_seconds": limit_s,
            "measured_operated_seconds": t_op,
            "table_row_index": row_index,
            "upper_bound_seconds": bound,
        },
        tolerance={"relative": _STARTUP_REL, "absolute_seconds": _STARTUP_ABS_S},
    )


def _check_stall_timing(delay_s: float, t_op: float, *, row_index: int) -> ProtectionEngineeringCheck:
    bound = delay_s * (1.0 + _STALL_UPPER_REL) + _STALL_UPPER_ABS_S
    st = "PASS" if t_op <= bound else "WARN" if t_op <= bound * 1.1 else "FAIL"
    return ProtectionEngineeringCheck(
        type="stall_during_run_timing_consistency",
        status=st,  # type: ignore[arg-type]
        message=None
        if st == "PASS"
        else "Operated time exceeds configured logic delay plus tolerance (trip slower than setting).",
        evidence={
            "logic_delay_seconds": delay_s,
            "measured_operated_seconds": t_op,
            "table_row_index": row_index,
            "upper_bound_seconds": bound,
        },
        tolerance={"relative": _STALL_UPPER_REL, "absolute_seconds": _STALL_UPPER_ABS_S},
    )


def _check_earth_fault_timing(
    expected_s: float,
    t_op: float | None,
    *,
    row_index: int | None,
    raw_cell: str | None,
) -> ProtectionEngineeringCheck:
    ev: dict[str, Any] = {
        "expected_time_seconds": expected_s,
        "measured_operated_seconds": t_op,
        "table_row_index": row_index,
        "raw_operated_cell": raw_cell,
    }
    if t_op is None:
        return ProtectionEngineeringCheck(
            type="earth_fault_timing_consistency",
            status="SKIP",
            message="Operated time cell is non-numeric; cannot compare to setting.",
            evidence=ev,
            tolerance={"relative": _EARTH_REL, "absolute_seconds": _EARTH_ABS_S},
        )
    tol = max(_EARTH_ABS_S, _EARTH_REL * max(expected_s, 1e-9))
    diff = abs(t_op - expected_s)
    st = "PASS" if diff <= tol else "WARN" if diff <= tol * 1.5 else "FAIL"
    return ProtectionEngineeringCheck(
        type="earth_fault_timing_consistency",
        status=st,  # type: ignore[arg-type]
        message=None if st == "PASS" else f"|measured - setting| = {diff:.4g}s vs tol {tol:.4g}s.",
        evidence={**ev, "absolute_difference_seconds": diff},
        tolerance={"relative": _EARTH_REL, "absolute_seconds": _EARTH_ABS_S},
    )


def _aggregate_status(checks: list[ProtectionEngineeringCheck]) -> str:
    if not checks:
        return "SKIP"
    if any(c.status == "FAIL" for c in checks):
        return "FAIL"
    if any(c.status == "WARN" for c in checks):
        return "WARN"
    if all(c.status == "SKIP" for c in checks):
        return "SKIP"
    return "PASS"


def _norm_blocks(metadata_blocks: Sequence[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not metadata_blocks:
        return out
    for b in metadata_blocks:
        if not isinstance(b, dict):
            continue
        n = b.get("normalized")
        if isinstance(n, dict):
            out.append(n)
    return out


def validate_protection_operation_measurements(
    *,
    heading_normalized: str,
    metadata_blocks: Sequence[dict[str, Any]] | None,
    tables: Sequence[dict[str, Any]] | None,
) -> ProtectionOperationValidationResult:
    """
    Run engineering checks for one section using normalized metadata blocks and extracted tables.

    ``metadata_blocks`` entries are typically ``ProtectionMetadataBlock.model_dump()`` dicts.
    ``tables`` entries match ``SectionTableData.model_dump()`` shape.
    """
    checks: list[ProtectionEngineeringCheck] = []
    hn = heading_normalized.upper()
    trip_tabs = _iter_trip_tables(tables)
    norms = _norm_blocks(metadata_blocks)

    # --- SHORT CIRCUIT (DTOC) ---
    if "SHORT CIRCUIT" in hn:
        delay = next((n.get("delay_seconds") for n in norms if n.get("delay_seconds") is not None), None)
        tab = trip_tabs[0] if trip_tabs else None
        pair = _first_numeric_injected_operated_pair(tab) if tab else None
        raw0 = metadata_blocks[0].get("raw_metadata_text") if metadata_blocks else None
        if delay is not None and pair:
            ri, _inj, top = pair
            checks.append(
                _check_dtoc_delay(
                    delay_s=float(delay),
                    t_meas=top,
                    raw_meta=str(raw0) if raw0 else None,
                    row_index=ri,
                )
            )
        else:
            checks.append(
                ProtectionEngineeringCheck(
                    type="dtoc_delay_consistency",
                    status="SKIP",
                    message="Missing delay setting or numeric trip table row.",
                    evidence={"heading_normalized": heading_normalized},
                )
            )

    elif "THERMAL" in hn and ("O/L" in hn or "OVERLOAD" in hn):
        tab = trip_tabs[0] if trip_tabs else None
        pair = _first_numeric_calc_operated_pair(tab) if tab else None
        if pair:
            ri, tc, op = pair
            checks.append(_check_thermal_timing(tc, op, row_index=ri))
        else:
            checks.append(
                ProtectionEngineeringCheck(
                    type="thermal_overload_timing_consistency",
                    status="SKIP",
                    message="Missing calculated/operated time columns or numeric row.",
                    evidence={"heading_normalized": heading_normalized},
                )
            )

    elif "NEGATIVE SEQUENCE" in hn:
        raw_d: str | None = None
        dt_block: dict[str, Any] | None = None
        for b in metadata_blocks or []:
            if not isinstance(b, dict):
                continue
            n = b.get("normalized") or {}
            if n.get("curve_type") == "DT" and n.get("delay_seconds") is not None:
                dt_block = n
                r = b.get("raw_metadata_text")
                raw_d = str(r) if r is not None else None
                break
        tab0 = trip_tabs[0] if trip_tabs else None
        if dt_block and tab0:
            pair = _first_numeric_injected_operated_pair(tab0)
            if pair:
                ri, _i, top = pair
                checks.append(
                    _check_dtoc_delay(
                        delay_s=float(dt_block["delay_seconds"]),
                        t_meas=top,
                        raw_meta=raw_d,
                        row_index=ri,
                    )
                )
            else:
                checks.append(
                    ProtectionEngineeringCheck(
                        type="dtoc_delay_consistency",
                        status="SKIP",
                        message="DTOC stage table row not numeric.",
                        evidence={"stage": "negative_sequence_stage1"},
                    )
                )
        else:
            checks.append(
                ProtectionEngineeringCheck(
                    type="dtoc_delay_consistency",
                    status="SKIP",
                    message="No DT delay metadata or primary trip table for stage 1.",
                    evidence={"heading_normalized": heading_normalized},
                )
            )

        idmt_norm: dict[str, Any] | None = None
        for n in norms:
            if n.get("tms") is not None and n.get("curve_type"):
                idmt_norm = n
                break
        tab1 = trip_tabs[1] if len(trip_tabs) > 1 else None
        if tab1 and idmt_norm:
            pts = _extract_idmt_injected_operated_points(tab1)
            if pts and len(pts) >= 2:
                checks.append(_check_inverse_time_monotonicity(pts))
                iref = min(p[0] for p in pts)
                ks: list[float] = []
                if iref > 0:
                    for i_a, t_a in pts:
                        r = max(i_a / iref, 1e-9)
                        den = abs(r**_IEC_SI_ALPHA - 1.0)
                        if den > 1e-5:
                            ks.append(t_a * den)
                if len(ks) >= 2:
                    k_mean = sum(ks) / len(ks)
                    spread = max(abs(k - k_mean) for k in ks) / max(k_mean, 1e-9)
                    tol_k = 0.28
                    st = "PASS" if spread <= tol_k else "WARN"
                    checks.append(
                        ProtectionEngineeringCheck(
                            type="inverse_time_si_curve_shape",
                            status=st,  # type: ignore[arg-type]
                            message=None
                            if st == "PASS"
                            else "Scatter of t*|M^0.02-1| across points exceeds loose SI-shape band.",
                            evidence={
                                "k_samples": ks,
                                "relative_spread": spread,
                                "I_ref_amperes": iref,
                                "tms_from_metadata": idmt_norm.get("tms"),
                                "curve_type": idmt_norm.get("curve_type"),
                            },
                            tolerance={"max_relative_spread": tol_k, "iec_si_alpha": _IEC_SI_ALPHA},
                        )
                    )
            else:
                checks.append(
                    ProtectionEngineeringCheck(
                        type="inverse_time_monotonicity",
                        status="SKIP",
                        message="Could not extract multi-point injection/operated columns for IDMT table.",
                        evidence={"table_headers": tab1.get("headers")},
                    )
                )
        else:
            checks.append(
                ProtectionEngineeringCheck(
                    type="inverse_time_monotonicity",
                    status="SKIP",
                    message="Missing IDMT metadata (curve/TMS) or second trip table.",
                    evidence={"heading_normalized": heading_normalized},
                )
            )

    elif "STARTUP" in hn or "PROLONGED START" in hn:
        limit = next(
            (n.get("startup_time_limit_seconds") for n in norms if n.get("startup_time_limit_seconds")), None
        )
        tab = trip_tabs[0] if trip_tabs else None
        pair = _first_numeric_injected_operated_pair(tab) if tab else None
        if limit is not None and pair:
            ri, _inj, top = pair
            checks.append(_check_startup_timing(float(limit), top, row_index=ri))
        else:
            checks.append(
                ProtectionEngineeringCheck(
                    type="startup_supervision_timing_consistency",
                    status="SKIP",
                    message="Missing startup time limit in metadata or numeric operated time.",
                    evidence={"heading_normalized": heading_normalized},
                )
            )

    elif "STALL" in hn and "RUNNING" in hn:
        delay = next(
            (n.get("stall_logic_delay_seconds") for n in norms if n.get("stall_logic_delay_seconds")), None
        )
        tab = trip_tabs[0] if trip_tabs else None
        pair = _first_numeric_injected_operated_pair(tab) if tab else None
        if delay is not None and pair:
            ri, _inj, top = pair
            checks.append(_check_stall_timing(float(delay), top, row_index=ri))
        else:
            checks.append(
                ProtectionEngineeringCheck(
                    type="stall_during_run_timing_consistency",
                    status="SKIP",
                    message="Missing stall logic delay or numeric operated time.",
                    evidence={"heading_normalized": heading_normalized},
                )
            )

    elif "EARTH FAULT" in hn or "E/F" in hn.upper():
        expected = next(
            (n.get("earth_fault_time_seconds") for n in norms if n.get("earth_fault_time_seconds")), None
        )
        tab = trip_tabs[0] if trip_tabs else None
        if expected is not None and tab:
            headers = list(tab.get("headers") or [])
            rows = tab.get("rows") or []
            i_op = _find_col_index(headers, "OPERATED")
            raw_cell: str | None = None
            t_op: float | None = None
            ri: int | None = None
            if i_op is not None:
                for rj, row in enumerate(rows):
                    if i_op < len(row):
                        raw_cell = str(row[i_op])
                        t_op = _parse_float_cell(row[i_op])
                        ri = rj
                        break
            checks.append(_check_earth_fault_timing(float(expected), t_op, row_index=ri, raw_cell=raw_cell))
        else:
            checks.append(
                ProtectionEngineeringCheck(
                    type="earth_fault_timing_consistency",
                    status="SKIP",
                    message="Missing earth-fault time setting or trip table.",
                    evidence={"heading_normalized": heading_normalized},
                )
            )

    else:
        return ProtectionOperationValidationResult(status="SKIP", checks=[])

    agg = _aggregate_status(checks)
    return ProtectionOperationValidationResult(status=agg, checks=checks)  # type: ignore[arg-type]


__all__ = ["validate_protection_operation_measurements", "_IEC_SI_ALPHA"]
