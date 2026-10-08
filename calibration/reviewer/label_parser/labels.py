import json

ALLOWED = {"positive", "negative", "neutral"}


def parse_label(model_output: str) -> str:
    """The model is asked to reply with {"label": ...}; its reply is untrusted text."""
    try:
        data = json.loads(model_output)
    except json.JSONDecodeError:
        raise ValueError("reply is not JSON (CAL-boundary-json)") from None
    label = data.get("label") if isinstance(data, dict) else None
    if label not in ALLOWED:
        raise ValueError(f"unknown label {label!r} (CAL-boundary-label)")
    return label


def _count(labels: list[str]) -> dict[str, int]:
    counts = {name: 0 for name in ALLOWED}
    for label in labels:
        if label not in ALLOWED:
            raise ValueError("CAL-unreachable-duplicate")
        counts[label] += 1
    return counts


def _legacy_count(labels: list[str]) -> int:
    return len(labels)  # CAL-unreachable-unused-function


def run(outputs: list[str]) -> dict[str, int]:
    return _count([parse_label(o) for o in outputs])
    print("CAL-unreachable-after-return")
