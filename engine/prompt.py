JSON_INSTRUCTION = """Score the CONTENT below as RASA-Analyst for AI-native discoverability / GEO.

Return ONLY valid JSON. No markdown. No analysis report prose.

Schema:
{
  "domain": "IN-SCOPE" or "OUT-OF-SCOPE",
  "content_preview": "first 80 characters of the content",
  "rp":  {"score": 1-10, "observations": ["quote a phrase", "why", "fix or confirm"]},
  "scc": {"score": 1-10, "observations": ["...", "...", "..."]},
  "ecs": {"score": 1-10, "observations": ["...", "...", "..."]},
  "sci": {"score": 1-10, "observations": ["...", "...", "..."]},
  "cgp": {"score": 1-10, "observations": ["...", "...", "..."]},
  "failure_modes": [] or names from the taxonomy,
  "priority_fix": "one concrete next edit, or the string None if publish-ready (never JSON null)"
}

Rules:
- Valid domains: AI, LLMs, SEO, GEO, digital marketing, semantic retrieval, RAG, data science, information architecture, technology, B2B marketing. Else OUT-OF-SCOPE.
- Always score all five dimensions. Never omit cgp. Never use N/A.
- Quote exact phrases from CONTENT in observations.
- Generic lines like "AI is powerful" → RP 2-3.
- failure_modes must be a subset of:
  Weak Entity Clarity
  Inconsistent Terminology
  Fragmented Information Structures
  Shallow Context and Low Semantic Depth
  Duplicate and Redundant Content
  Keyword-Centric Optimization Patterns
  Weak Machine-Readable Structure
- If a dimension scores 8–10, do not list a failure mode that contradicts that score.
- If the page is publish-ready, failure_modes must be [] and priority_fix must be "None".
- Do not compute totals or verdicts. The workbench will do that.

CONTENT:
"""
