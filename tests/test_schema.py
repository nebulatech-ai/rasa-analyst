from __future__ import annotations

from engine.schema import ModelJudgement, finalize


def _dim(score: int, *obs: str) -> dict:
    return {"score": score, "observations": list(obs) or [f"score {score}"]}


def _judgement(**kwargs) -> ModelJudgement:
    base = {
        "domain": "IN-SCOPE",
        "content_preview": "preview",
        "rp": _dim(9, 'Named entity "RASA" is defined.'),
        "scc": _dim(9, "Chunks stay on one idea."),
        "ecs": _dim(9, "Org name is explicit."),
        "sci": _dim(9, "Answer-shaped sentences."),
        "cgp": _dim(9, "DOI is citable."),
        "failure_modes": [],
        "priority_fix": "None",
    }
    base.update(kwargs)
    return ModelJudgement.model_validate(base)


def test_out_of_scope_forces_rp_one_and_reject():
    result = finalize(
        _judgement(domain="OUT-OF-SCOPE", rp=_dim(8, "Would look on-topic.")),
        model="nebulatech/rasa-analyst:latest",
        seed=1,
        content="Grandma sourdough recipe with flour and water.",
    )
    assert result.verdict == "REJECT"
    rp = next(d for d in result.dimensions if d.key == "RP")
    assert rp.score == 1
    assert result.content_preview.startswith("Grandma sourdough")


def test_publish_clears_contradictory_failures_and_fix():
    result = finalize(
        _judgement(
            failure_modes=["Weak Entity Clarity", "Keyword-Centric Optimization Patterns"],
            priority_fix="Add more keywords to the hero.",
        ),
        model="m",
        seed=2,
        content='RASA is defined here with a DOI.',
    )
    assert result.geo_readiness == 9.0
    assert result.verdict == "PUBLISH"
    assert result.failure_modes == []
    assert result.priority_fix == "None"


def test_revise_keeps_failure_and_fills_empty_fix():
    low = _dim(6, "Needs a tighter entity.")
    result = finalize(
        _judgement(
            rp=low,
            scc=low,
            ecs=low,
            sci=low,
            cgp=low,
            failure_modes=["Weak Entity Clarity"],
            priority_fix="None",
        ),
        model="m",
        seed=3,
    )
    assert result.verdict == "REVISE"
    assert result.geo_readiness == 6.0
    assert result.failure_modes == ["Weak Entity Clarity"]
    assert result.priority_fix.startswith("Address:")


def test_reject_below_six():
    low = _dim(4, "Thin.")
    result = finalize(_judgement(rp=low, scc=low, ecs=low, sci=low, cgp=low), model="m")
    assert result.verdict == "REJECT"
    assert result.geo_readiness == 4.0


def test_null_fix_and_failures_coerce():
    j = ModelJudgement.model_validate(
        {
            "domain": "IN-SCOPE",
            "content_preview": "x",
            "rp": _dim(8, "a"),
            "scc": _dim(8, "b"),
            "ecs": _dim(8, "c"),
            "sci": _dim(8, "d"),
            "cgp": _dim(8, "e"),
            "failure_modes": None,
            "priority_fix": None,
        }
    )
    assert j.priority_fix == "None"
    assert j.failure_modes == []


def test_strong_ecs_drops_weak_entity_failure_on_revise():
    result = finalize(
        _judgement(
            rp=_dim(7, "ok"),
            scc=_dim(7, "ok"),
            ecs=_dim(9, 'Entity "Nebula Personalization Tech Solutions Pvt. Ltd." is named.'),
            sci=_dim(7, "ok"),
            cgp=_dim(7, "ok"),
            failure_modes=["Weak Entity Clarity", "Shallow Context and Low Semantic Depth"],
            priority_fix="Deepen the synthesis paragraph.",
        ),
        model="m",
        seed=4,
        content='Nebula Personalization Tech Solutions Pvt. Ltd. ships RASA.',
    )
    assert result.verdict == "REVISE"
    assert "Weak Entity Clarity" not in result.failure_modes
    assert "Shallow Context and Low Semantic Depth" in result.failure_modes


def test_quoted_observation_must_appear_in_content():
    result = finalize(
        _judgement(rp=_dim(9, 'Cites "this phrase is absent xyzzy"', "Fallback without quotes.")),
        model="m",
        content="RASA defines retrieval-aware architectures for GEO.",
    )
    rp = next(d for d in result.dimensions if d.key == "RP")
    assert rp.observations == ["Fallback without quotes."]
