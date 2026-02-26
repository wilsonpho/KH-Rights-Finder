from dataclasses import dataclass, field


@dataclass
class ScoreBreakdown:
    total: int = 0
    authoritative: int = 0
    secondary: int = 0
    label: str = "none"
    factors: list[dict] = field(default_factory=list)


def compute_score(evidence_rows: list[dict]) -> ScoreBreakdown:
    auth_evidence = [e for e in evidence_rows if e.get("source_type") == "authoritative"]
    sec_evidence = [e for e in evidence_rows if e.get("source_type") == "secondary"]

    auth_score = 0
    factors: list[dict] = []

    # Factor 1: D/IPR Trademark Registration (0-60 pts)
    trademark_hits = [e for e in auth_evidence if e.get("source") == "dip_trademark"]
    if trademark_hits:
        best_status = _best_trademark_status(trademark_hits)
        pts = {"registered": 60, "pending": 30, "expired": 10}.get(best_status, 15)
        auth_score += pts
        factors.append({"source": "dip_trademark", "status": best_status, "points": pts})

    # Factor 2: D/IPR Exclusive Rights (0-40 pts)
    exclusive_hits = [e for e in auth_evidence if e.get("source") == "dip_exclusive"]
    if exclusive_hits:
        pts = 40
        auth_score += pts
        factors.append({"source": "dip_exclusive", "status": None, "points": pts})

    total = min(auth_score, 100)
    sec_score = min(len(sec_evidence) * 25, 100)

    label = (
        "strong" if total >= 70 else
        "moderate" if total >= 40 else
        "weak" if total > 0 else
        "none"
    )

    return ScoreBreakdown(
        total=total,
        authoritative=total,
        secondary=sec_score,
        label=label,
        factors=factors,
    )


def _best_trademark_status(hits: list[dict]) -> str:
    statuses = []
    for h in hits:
        detail = h.get("detail") or {}
        statuses.append((detail.get("status") or "").lower())
    for preferred in ["registered", "pending", "expired"]:
        if any(preferred in s for s in statuses):
            return preferred
    return "unknown"
