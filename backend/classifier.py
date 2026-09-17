"""
Keyword-based comment classifier.
Maps free-text passenger comments to structured complaint categories and severity.

Example usage:
    classify("The bus is always packed after 6 PM.")
    → {"category": "Crowding", "severity": "medium", "confidence": 0.85}
"""

import re
from typing import TypedDict


class ClassificationResult(TypedDict):
    category: str
    severity: str
    confidence: float


# ---------------------------------------------------------------------------
# Keyword taxonomy — each entry: (pattern_list, category, base_severity)
# ---------------------------------------------------------------------------
TAXONOMY: list[tuple[list[str], str, str]] = [
    # Safety — always HIGH severity
    (
        [
            r"harass", r"assault", r"attack", r"threaten", r"threat",
            r"fight", r"violence", r"violent", r"weapon", r"knife", r"gun",
            r"unsafe", r"dangerous", r"danger", r"scared", r"afraid",
            r"robbery", r"theft", r"stole",
        ],
        "Safety",
        "high",
    ),
    # Driver Behaviour — MEDIUM severity
    (
        [
            r"driver", r"operator", r"rude", r"aggressive", r"impolite",
            r"yell", r"yelled", r"screamed", r"ignored", r"dismiss",
            r"skip(ped)? (the )?stop", r"pass(ed)? (the )?stop",
            r"didn'?t stop", r"refused", r"speeding", r"speed",
            r"ran (a )?red", r"phone while driving", r"distract",
            r"unprofessional",
        ],
        "Driver Behaviour",
        "medium",
    ),
    # Delays / Punctuality — MEDIUM severity
    (
        [
            r"late", r"delay", r"never on time", r"long wait",
            r"waiting (for|so long)", r"behind schedule", r"overdue",
            r"slow", r"didn'?t come", r"no bus", r"skipped my stop",
            r"hour(s)? wait", r"min(ute)?s? wait", r"not show(ing)?",
            r"running late", r"always late", r"punctual",
        ],
        "Delays",
        "medium",
    ),
    # Crowding — LOW severity (sometimes medium at rush hour)
    (
        [
            r"pack(ed)?", r"overcrowd", r"crowd(ed)?", r"standing room",
            r"no seat", r"full bus", r"jam(med)?", r"cramp(ed)?",
            r"squish(ed)?", r"sardine", r"too many people", r"capacity",
            r"can'?t get on", r"couldn'?t board",
        ],
        "Crowding",
        "low",
    ),
    # Cleanliness — LOW severity
    (
        [
            r"dirt(y)?", r"filth(y)?", r"smell(s)?", r"odor", r"stink",
            r"trash", r"garbage", r"litter", r"graffiti", r"stain(ed)?",
            r"grim(y|e)?", r"unhygien", r"unclean", r"mess(y)?",
            r"vomit", r"pee", r"urine",
        ],
        "Cleanliness",
        "low",
    ),
    # Mechanical Issues — MEDIUM severity
    (
        [
            r"breakdown", r"broke down", r"broken", r"malfunction",
            r"air (con|condition)", r"\bac\b", r"heat(er)?", r"door(s)?",
            r"engine", r"technical", r"not working", r"out of service",
            r"stuck", r"vehicle", r"bus broke",
        ],
        "Mechanical Issues",
        "medium",
    ),
    # Service / Route Issues — LOW-MEDIUM
    (
        [
            r"route (change|changed|cancel)", r"detour", r"stop (remov|cancel|clos)",
            r"reroute", r"different route", r"wrong stop", r"wrong route",
            r"not running", r"cancelled", r"no service", r"info(rmation)?",
            r"schedule (change|wrong|incorrect)",
        ],
        "Service Issues",
        "medium",
    ),
]

CATEGORY_PRIORITY = {
    "Safety": 7,
    "Driver Behaviour": 6,
    "Mechanical Issues": 5,
    "Delays": 4,
    "Service Issues": 3,
    "Crowding": 2,
    "Cleanliness": 1,
}


def classify(comment: str) -> ClassificationResult:
    """
    Classify a free-text comment into a category and severity level.

    Args:
        comment: Raw passenger comment text.

    Returns:
        ClassificationResult with category, severity, and confidence score.
    """
    if not comment or not comment.strip():
        return ClassificationResult(
            category="General", severity="low", confidence=0.5
        )

    text = comment.lower()
    matches: list[tuple[str, str, int]] = []  # (category, severity, match_count)

    for patterns, category, base_severity in TAXONOMY:
        count = sum(
            1 for p in patterns if re.search(p, text)
        )
        if count > 0:
            matches.append((category, base_severity, count))

    if not matches:
        return ClassificationResult(
            category="General", severity="low", confidence=0.4
        )

    # Pick category with highest priority, breaking ties by match count
    matches.sort(key=lambda x: (CATEGORY_PRIORITY.get(x[0], 0), x[2]), reverse=True)
    best_category, best_severity, best_count = matches[0]

    # Escalate severity for very strong signals
    if best_count >= 3 and best_severity == "low":
        best_severity = "medium"
    if best_count >= 3 and best_severity == "medium":
        best_severity = "high"

    # Confidence: based on how many patterns matched relative to total patterns
    total_patterns = sum(
        len(p) for p, _, _ in TAXONOMY
        if _ == best_category or any(c == best_category for c in [_])
    )
    confidence = min(0.95, 0.55 + best_count * 0.12)

    return ClassificationResult(
        category=best_category,
        severity=best_severity,
        confidence=round(confidence, 2),
    )


def batch_classify(comments: list[str]) -> list[ClassificationResult]:
    """Classify a list of comments in bulk."""
    return [classify(c) for c in comments]


# ---------------------------------------------------------------------------
# Mapping from 311 complaint_type / descriptor → our categories
# ---------------------------------------------------------------------------
NYC_311_CATEGORY_MAP: dict[str, str] = {
    "Bus": "Service Issues",
    "Bus Stop": "Service Issues",
    "MTA Bus": "Service Issues",
    "Transit Authority Bus": "Driver Behaviour",
    "Graffiti": "Cleanliness",
    "Dirty Conditions": "Cleanliness",
    "Noise": "General",
    "Overcrowding": "Crowding",
}


def map_311_complaint(complaint_type: str, descriptor: str) -> ClassificationResult:
    """
    Map a 311 service request complaint_type + descriptor to our categories.
    First tries keyword classification on the descriptor, then falls back to
    the hardcoded category map.
    """
    result = classify(f"{complaint_type} {descriptor}")
    if result["category"] == "General":
        mapped = NYC_311_CATEGORY_MAP.get(complaint_type, "General")
        result = ClassificationResult(
            category=mapped,
            severity=result["severity"],
            confidence=0.6,
        )
    return result
