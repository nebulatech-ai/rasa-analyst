from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from engine.version import ENGINE

Domain = Literal["IN-SCOPE", "OUT-OF-SCOPE"]
Band = Literal["STRONG", "MODERATE", "WEAK"]
Verdict = Literal["PUBLISH", "REVISE", "REJECT"]

DIM_KEYS = ("rp", "scc", "ecs", "sci", "cgp")
DIM_LABELS = {
    "rp": "Retrieval Probability",
    "scc": "Semantic Chunk Coherence",
    "ecs": "Entity Clarity Score",
    "sci": "Synthesis Compatibility Index",
    "cgp": "Citation & Grounding Potential",
}
WEIGHTS = {"rp": 0.25, "scc": 0.20, "ecs": 0.20, "sci": 0.20, "cgp": 0.15}

FAILURE_TAXONOMY = [
    "Weak Entity Clarity",
    "Inconsistent Terminology",
    "Fragmented Information Structures",
    "Shallow Context and Low Semantic Depth",
    "Duplicate and Redundant Content",
    "Keyword-Centric Optimization Patterns",
    "Weak Machine-Readable Structure",
]

# Drop a failure mode when its related dimension is already STRONG.
FAILURE_GATES: dict[str, tuple[str, int]] = {
    "Weak Entity Clarity": ("ecs", 8),
    "Inconsistent Terminology": ("ecs", 8),
    "Fragmented Information Structures": ("scc", 8),
    "Shallow Context and Low Semantic Depth": ("sci", 8),
    "Duplicate and Redundant Content": ("scc", 8),
    "Keyword-Centric Optimization Patterns": ("rp", 8),
    "Weak Machine-Readable Structure": ("sci", 8),
}


class DimensionScore(BaseModel):
    score: int = Field(ge=1, le=10)
    observations: list[str] = Field(min_length=1, max_length=5)

    @field_validator("observations")
    @classmethod
    def strip_obs(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s and s.strip()]
        if not cleaned:
            raise ValueError("at least one observation required")
        return cleaned[:5]


class ModelJudgement(BaseModel):
    """What the LLM is allowed to decide. Math and verdict are computed in code."""

    domain: Domain
    content_preview: str = Field(max_length=200)
    rp: DimensionScore
    scc: DimensionScore
    ecs: DimensionScore
    sci: DimensionScore
    cgp: DimensionScore
    failure_modes: list[str] = Field(default_factory=list)
    priority_fix: str = Field(default="None", min_length=4, max_length=400)

    @field_validator("priority_fix", mode="before")
    @classmethod
    def coerce_priority_fix(cls, v: Any) -> str:
        if v is None:
            return "None"
        if isinstance(v, str):
            text = v.strip()
            return text if len(text) >= 4 else "None"
        return str(v)

    @field_validator("failure_modes", mode="before")
    @classmethod
    def coerce_failures(cls, v: Any) -> list:
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return v

    @field_validator("failure_modes")
    @classmethod
    def known_failures(cls, v: list[str]) -> list[str]:
        allowed = set(FAILURE_TAXONOMY)
        out = []
        for item in v:
            name = item.strip()
            if name in allowed and name not in out:
                out.append(name)
        return out


class WeightedRow(BaseModel):
    key: str
    label: str
    score: int
    band: Band
    weight: float
    weighted: float
    observations: list[str]


class AnalysisResult(BaseModel):
    domain: Domain
    content_preview: str
    dimensions: list[WeightedRow]
    total: float
    geo_readiness: float
    verdict: Verdict
    failure_modes: list[str]
    priority_fix: str
    model: str
    engine: str = ENGINE
    seed: int | None = None


def band_for(score: int) -> Band:
    if score >= 8:
        return "STRONG"
    if score >= 5:
        return "MODERATE"
    return "WEAK"


def _preview(content: str | None, fallback: str) -> str:
    src = (content or fallback or "").strip().replace("\n", " ")
    src = " ".join(src.split())
    return src[:80]


def _none_fix(text: str) -> bool:
    return bool(
        text
        and any(x in text.lower() for x in ("none", "no change", "no fix", "n/a"))
    )


def _filter_failures(names: list[str], scores: dict[str, DimensionScore]) -> list[str]:
    kept: list[str] = []
    for name in names:
        gate = FAILURE_GATES.get(name)
        if gate:
            key, floor = gate
            if scores[key].score >= floor:
                continue
        kept.append(name)
    return kept


def _ground_obs(obs: list[str], content: str | None) -> list[str]:
    if not content:
        return obs[:3]
    blob = content.casefold()
    grounded: list[str] = []
    for line in obs:
        quotes = [q.strip() for q in line.split('"')[1::2] if len(q.strip()) >= 6]
        if quotes and not any(q.casefold() in blob for q in quotes):
            continue
        grounded.append(line)
    return (grounded or obs)[:3]


def finalize(
    judgement: ModelJudgement,
    model: str,
    seed: int | None = None,
    content: str | None = None,
) -> AnalysisResult:
    scores = {k: getattr(judgement, k) for k in DIM_KEYS}
    if judgement.domain == "OUT-OF-SCOPE":
        scores["rp"] = DimensionScore(
            score=1,
            observations=list(scores["rp"].observations)
            + ["Domain gate: out-of-scope content cannot score RP above 1."],
        )

    rows: list[WeightedRow] = []
    total = 0.0
    for key in DIM_KEYS:
        dim = scores[key]
        w = WEIGHTS[key]
        weighted = round(dim.score * w, 2)
        total += weighted
        rows.append(
            WeightedRow(
                key=key.upper(),
                label=DIM_LABELS[key],
                score=dim.score,
                band=band_for(dim.score),
                weight=w,
                weighted=weighted,
                observations=_ground_obs(dim.observations, content),
            )
        )

    total = round(total, 2)
    if judgement.domain == "OUT-OF-SCOPE" or total < 6.0:
        verdict: Verdict = "REJECT"
    elif total >= 8.0:
        verdict = "PUBLISH"
    else:
        verdict = "REVISE"

    failures = _filter_failures(judgement.failure_modes, scores)
    fix = judgement.priority_fix.strip() or "None"
    if verdict == "PUBLISH":
        failures = []
        if not _none_fix(fix):
            fix = "None"
    elif _none_fix(fix) and failures:
        fix = f"Address: {failures[0]}"

    return AnalysisResult(
        domain=judgement.domain,
        content_preview=_preview(content, judgement.content_preview),
        dimensions=rows,
        total=total,
        geo_readiness=total,
        verdict=verdict,
        failure_modes=failures,
        priority_fix=fix,
        model=model,
        engine=ENGINE,
        seed=seed,
    )
