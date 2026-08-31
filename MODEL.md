---
title: nebulatech/rasa-analyst
engine: rasa-analyst-workbench/1.0.0
---

# RASA-Analyst

Local GEO / AI-native discoverability scorer from **Nebula Personalization Tech Solutions Pvt. Ltd.**

## Use the workbench, not chat

```text
ollama pull nebulatech/rasa-analyst
```

Then run the workbench in this repository (`start.bat` or `start.sh`). The model only returns five 1–10 scores. Totals and PUBLISH / REVISE / REJECT are computed in code.

Do not treat `ollama run nebulatech/rasa-analyst` as the product. Chat will invent arithmetic.

## Thresholds

- PUBLISH ≥ 8.0  
- REVISE 6.0–7.9  
- REJECT < 6.0 or OUT-OF-SCOPE (RP forced to 1)

Weights: RP 0.25, SCC 0.20, ECS 0.20, SCI 0.20, CGP 0.15

## Privacy

Paste and file scoring stay on the machine. **From URL** fetches a public page only.

## License

Workbench: MIT (see `LICENSE`). Model: Llama 3.1 Community License (see `NOTICE`).
