"""Merge, deduplicate, and export section predictions."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from llm.section_detector import SectionPrediction

logger = logging.getLogger(__name__)


def _intervals_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (a_end < b_start or b_end < a_start)


def _merge_pair(
    left: SectionPrediction,
    right: SectionPrediction,
) -> SectionPrediction:
    """Merge two overlapping same-type spans."""
    start = min(left.start_line, right.start_line)
    end = max(left.end_line, right.end_line)
    title = (
        left.detected_title
        if left.confidence >= right.confidence
        else right.detected_title
    )
    confidence = max(left.confidence, right.confidence)
    return SectionPrediction(
        section_type=left.section_type,
        detected_title=title,
        start_line=start,
        end_line=end,
        confidence=confidence,
    )


def _merge_chain(chain: list[SectionPrediction]) -> list[SectionPrediction]:
    """Merge a sorted list of predictions that share the same ``section_type``."""
    merged: list[SectionPrediction] = []
    for pred in chain:
        if not merged:
            merged.append(pred)
            continue
        last = merged[-1]
        if _intervals_overlap(
            last.start_line, last.end_line, pred.start_line, pred.end_line
        ):
            merged[-1] = _merge_pair(last, pred)
        else:
            merged.append(pred)
    return merged


def merge_section_predictions(
    predictions: Iterable[SectionPrediction],
) -> list[SectionPrediction]:
    """
    Merge overlapping detections **per** ``section_type``, drop exact duplicates,
    then sort globally by ``start_line``.
    """
    items = list(predictions)
    if not items:
        return []

    deduped: dict[tuple[str, int, int], SectionPrediction] = {}
    for pred in items:
        key = (pred.section_type, pred.start_line, pred.end_line)
        existing = deduped.get(key)
        if existing is None or pred.confidence > existing.confidence:
            deduped[key] = pred

    by_type: dict[str, list[SectionPrediction]] = defaultdict(list)
    for pred in deduped.values():
        by_type[pred.section_type].append(pred)

    merged_all: list[SectionPrediction] = []
    for preds in by_type.values():
        preds.sort(key=lambda p: (p.start_line, p.end_line))
        merged_all.extend(_merge_chain(preds))

    merged_all.sort(key=lambda p: (p.start_line, p.end_line))
    logger.info("Merged pipeline produced %s sections", len(merged_all))
    return merged_all


def predictions_to_jsonable(predictions: list[SectionPrediction]) -> list[dict]:
    """Serialise predictions to plain dicts matching the public JSON schema."""
    return [
        {
            "section_type": p.section_type,
            "detected_title": p.detected_title,
            "start_line": p.start_line,
            "end_line": p.end_line,
            "confidence": round(float(p.confidence), 4),
        }
        for p in predictions
    ]


def export_sections_json(
    predictions: list[SectionPrediction],
    destination: Path,
) -> None:
    """Write merged sections to ``destination`` as UTF-8 JSON."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = predictions_to_jsonable(predictions)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote %s sections to %s", len(payload), destination)
