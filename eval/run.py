"""Locked live eval against local Ollama. Does not change scoring weights.

Usage (from rasa-analyst/):
  .venv\\Scripts\\python.exe -m eval.run
  .venv\\Scripts\\python.exe -m eval.run --repeats 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from engine.client import OllamaError, analyze_content
from engine.schema import AnalysisResult, finalize
from engine.version import DEFAULT_MODEL, ENGINE

ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "cases.json"
OUT_DIR = ROOT / "out"


def _dim(result: AnalysisResult, key: str):
    return next(d for d in result.dimensions if d.key == key.upper())


def check_case(result: AnalysisResult, content: str, expect: dict) -> list[str]:
    fails: list[str] = []
    if expect.get("domain") and result.domain != expect["domain"]:
        fails.append(f"domain {result.domain} != {expect['domain']}")
    if expect.get("verdict") and result.verdict != expect["verdict"]:
        fails.append(f"verdict {result.verdict} != {expect['verdict']}")
    allowed = expect.get("verdict_in")
    if allowed and result.verdict not in allowed:
        fails.append(f"verdict {result.verdict} not in {allowed}")
    if "rp_max" in expect:
        rp = _dim(result, "RP").score
        if rp > expect["rp_max"]:
            fails.append(f"RP {rp} > max {expect['rp_max']}")
    if "ecs_min" in expect:
        ecs = _dim(result, "ECS").score
        if ecs < expect["ecs_min"]:
            fails.append(f"ECS {ecs} < min {expect['ecs_min']}")
    for name in expect.get("forbidden_failures") or []:
        if name in result.failure_modes:
            fails.append(f"forbidden failure {name!r}")
    if expect.get("must_quote"):
        blob = content.casefold()
        quoted = False
        for row in result.dimensions:
            for line in row.observations:
                parts = [q.strip() for q in line.split('"')[1::2] if len(q.strip()) >= 6]
                if any(q.casefold() in blob for q in parts):
                    quoted = True
                if any(len(tok) >= 16 and tok.casefold() in blob for tok in [line]):
                    quoted = True
        if not quoted:
            fails.append("no observation quoted from content")
    return fails


async def run_once(content: str) -> AnalysisResult:
    judgement, seed = await analyze_content(content, model=DEFAULT_MODEL)
    return finalize(judgement, model=DEFAULT_MODEL, seed=seed, content=content)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Locked RASA-Analyst eval (live Ollama)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[: args.limit]

    rows = []
    hard_fail = 0
    jitter_warn = 0
    for case in cases:
        cid = case["id"]
        content = case["content"]
        expect = case["expect"]
        results: list[AnalysisResult] = []
        try:
            for _ in range(max(1, args.repeats)):
                results.append(await run_once(content))
        except OllamaError as e:
            hard_fail += 1
            rows.append({"id": cid, "ok": False, "fails": [str(e)], "jitter": []})
            print(f"FAIL  {cid}  {e}")
            continue

        fails = check_case(results[0], content, expect)
        jitter = []
        if len(results) > 1:
            for key in ("RP", "SCC", "ECS", "SCI", "CGP"):
                scores = [_dim(r, key).score for r in results]
                if max(scores) - min(scores) >= 2:
                    jitter.append(f"{key} {scores}")
            if jitter:
                jitter_warn += 1
        ok = not fails
        if not ok:
            hard_fail += 1
        extra = f"  jitter {jitter}" if jitter else ""
        print(f"{'PASS' if ok else 'FAIL'}  {cid}  {results[0].domain} {results[0].verdict} {results[0].geo_readiness:.2f}{extra}")
        for f in fails:
            print(f"      {f}")
        rows.append(
            {
                "id": cid,
                "ok": ok,
                "fails": fails,
                "jitter": jitter,
                "domain": results[0].domain,
                "verdict": results[0].verdict,
                "geo_readiness": results[0].geo_readiness,
                "engine": ENGINE,
                "model": DEFAULT_MODEL,
            }
        )

    OUT_DIR.mkdir(exist_ok=True)
    report = {
        "engine": ENGINE,
        "model": DEFAULT_MODEL,
        "repeats": args.repeats,
        "passed": sum(1 for r in rows if r.get("ok")),
        "failed": hard_fail,
        "jitter_warn": jitter_warn,
        "cases": rows,
    }
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print()
    print(f"{report['passed']} passed, {report['failed']} failed, {jitter_warn} jitter-warn")
    print(f"Wrote {OUT_DIR / 'report.json'}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
