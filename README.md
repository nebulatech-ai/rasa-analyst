# RASA-Analyst workbench

Local GEO scoring UI from **Nebula Personalization Tech Solutions Pvt. Ltd.**

Paste a page or snippet, run **Analyze**, and get a GEO readiness score. The large language model runs in **Ollama** on this machine. Weights and PUBLISH / REVISE / REJECT are calculated in this app — not by chat.

This is a GEO readiness aid, not a claim of access to ChatGPT or Gemini ranking internals.

Paper: Amit Verma & Sarita Agarwal, Retrieval-Aware Semantic Architectures for AI-Native Search Systems, [DOI 10.5281/zenodo.20325460](https://doi.org/10.5281/zenodo.20325460) · [RASA Framework](https://www.nebulatech.in/research/rasa)

## Launch

1. Install [Ollama](https://ollama.com) and start it.  
2. Pull the model:

```bash
ollama pull nebulatech/rasa-analyst
```

3. Python 3.11+ on the PATH.

**Windows**

```bat
cd rasa-analyst
start.bat
```

**macOS / Linux**

```bash
cd rasa-analyst
chmod +x start.sh
./start.sh
```

Open **http://127.0.0.1:8787**

The first run creates `.venv` and installs dependencies. Keep the terminal open while you score. Close it to stop the server. The app binds to localhost only.

Optional: copy `.env.example` to `.env` if Ollama is not on `http://127.0.0.1:11434`.

### Docker

Ollama stays on the host.

```bash
docker compose up --build -d
```

- Liveness: `GET /api/health`  
- Ready to score: `GET /api/ready` (503 until the model is pulled)

Do not put this on the public internet without a reverse proxy, authentication, and a review of **From URL** (it fetches public pages only).

## How to use

1. Paste copy, or fetch a public URL, or upload `.txt` / `.md` / `.html` / `.docx`.  
2. Confirm **Ollama connected**.  
3. **Analyze**. Scoring can take 20–90 seconds (longer on CPU).  
4. Read GEO readiness, PUBLISH / REVISE / REJECT, and the five dimensions. Copy report or download JSON if you need a brief.

Copy never leaves the machine except **From URL**.

## Why not `ollama run`

The model returns five 1–10 scores, observations, failure modes, and a priority fix. This workbench:

- forces JSON and retries once on invalid output  
- clamps out-of-scope **RP to 1** and **REJECT**  
- applies weights RP 0.25, SCC 0.20, ECS 0.20, SCI 0.20, CGP 0.15  
- sets **PUBLISH ≥ 8.0**, **REVISE 6.0–7.9**, **REJECT < 6.0**  
- uses temperature 0 and a seed from the pasted text (GPU can still move a score ±1)

## Tests and eval

Engine tests (no GPU):

```bash
.venv\Scripts\python.exe -m pytest
```

Locked live eval (needs Ollama + the model). Do not treat this as a unit test in CI unless Ollama is present:

```bash
.venv\Scripts\python.exe -m eval.run
.venv\Scripts\python.exe -m eval.run --repeats 3
```

Cases are in `eval/cases.json`. Gold labels are bands and gates, not a single 8.80 score. Reports write to `eval/out/report.json` (gitignored).

## License

Workbench: MIT (`LICENSE`). Model: Llama 3.1 Community License (`NOTICE`).
