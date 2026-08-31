const SAMPLE = `Retrieval-Aware Semantic Architectures (RASA), developed by Amit Verma and Sarita Agarwal at Nebula Personalization Tech Solutions Pvt. Ltd., defines five core principles for AI-native discoverability: Semantic Chunking, Entity-Centric Information Modeling, Hierarchical Contextual Organization, Machine-Readable Semantic Signals, and Synthesis Compatibility. Published at DOI: 10.5281/zenodo.20325460, the framework evaluates content for retrieval probability, synthesis compatibility, and citation-worthiness within generative AI pipelines including RAG systems.`;

const SAMPLE_OOS = `Grandma's Saturday sourdough: mix 500g bread flour, 350g water, 10g salt, and 100g starter. Bulk ferment 4 hours, shape, cold proof overnight, bake at 230°C in a Dutch oven for 40 minutes. Serve with cultured butter.`;

const MAX_CHARS = 20000;
let lastResult = null;
let activeTab = "paste";
let canScore = false;

const $ = (id) => document.getElementById(id);

function setStatus(state, text) {
  const el = $("status");
  el.dataset.state = state;
  el.innerHTML = `<span class="dot"></span> ${text}`;
}

function updateCount() {
  const n = ($("content").value || "").length;
  $("count").textContent = `${n.toLocaleString()} / ${MAX_CHARS.toLocaleString()}`;
}

function setRunEnabled(on) {
  canScore = on;
  $("run").disabled = !on;
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    activeTab = btn.dataset.tab;
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b === btn));
    document.querySelectorAll("[data-pane]").forEach((el) => {
      el.classList.toggle("hidden", el.dataset.pane !== activeTab);
    });
  });
});

$("content").addEventListener("input", updateCount);

async function health() {
  try {
    const h = await fetch("/api/ready").then((r) => r.json());
    if (!h.ollama) {
      setStatus("bad", "Ollama offline");
      setRunEnabled(false);
    } else if (!h.preferred_present) {
      setStatus("warn", "Model missing");
      setRunEnabled(false);
    } else {
      setStatus("ok", "Ollama connected");
      setRunEnabled(true);
      if (h.preferred) $("model-label").textContent = h.preferred;
    }
  } catch {
    setStatus("bad", "API unreachable");
    setRunEnabled(false);
  }
}

function showError(msg) {
  const el = $("error");
  el.hidden = !msg;
  el.textContent = msg || "";
}

function animateScore(el, value) {
  const start = performance.now();
  const dur = 480;
  const tick = (now) => {
    const p = Math.min(1, (now - start) / dur);
    const eased = 1 - (1 - p) ** 3;
    el.textContent = (value * eased).toFixed(2);
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function render(result) {
  lastResult = result;
  $("idle").hidden = true;
  $("result").hidden = false;
  const oos = result.domain === "OUT-OF-SCOPE";
  $("oos-hero").hidden = !oos;
  $("score-hero").hidden = oos;
  if (!oos) {
    animateScore($("total"), result.geo_readiness);
    const badge = $("verdict");
    badge.textContent = result.verdict;
    badge.className = "verdict " + result.verdict;
  }
  const bits = [result.domain, result.model, result.seed != null ? `seed ${result.seed}` : null, result.content_preview || null].filter(Boolean);
  $("meta").textContent = bits.join(" · ");
  const noneFix = /^(none|no change|no fix)\b/i.test(result.priority_fix.trim());
  $("fix").innerHTML = noneFix ? `<span class="none-ok">None</span>` : escapeHtml(result.priority_fix);
  const ul = $("failures");
  ul.innerHTML = "";
  if (!result.failure_modes.length) {
    ul.innerHTML = `<li class="none-ok">None detected</li>`;
  } else {
    result.failure_modes.forEach((f) => {
      const li = document.createElement("li");
      li.textContent = f;
      ul.appendChild(li);
    });
  }
  const bars = $("bars");
  bars.innerHTML = "";
  result.dimensions.forEach((d) => {
    const wrap = document.createElement("div");
    wrap.className = "dim-wrap";
    wrap.innerHTML = `
      <button type="button" class="dim">
        <div class="dim-top">
          <span class="name"><b>${d.key}</b> ${d.label}</span>
          <span class="n">${Number(d.score).toFixed(1)} / 10</span>
          <span class="band ${d.band}">${d.band}</span>
        </div>
        <div class="track"><div class="fill" data-w="${d.score * 10}"></div></div>
      </button>
      <ul class="obs">${d.observations.map((o) => `<li>${escapeHtml(o)}</li>`).join("")}</ul>
    `;
    wrap.querySelector(".dim").addEventListener("click", () => wrap.classList.toggle("open"));
    bars.appendChild(wrap);
  });
  requestAnimationFrame(() => {
    bars.querySelectorAll(".fill").forEach((el) => {
      el.style.width = `${el.dataset.w}%`;
    });
  });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function reportText(r) {
  const dims = r.dimensions
    .map((d) => `${d.key} ${d.score}/10 ${d.band} (×${d.weight} = ${d.weighted.toFixed(2)})\n` + d.observations.map((o) => `  • ${o}`).join("\n"))
    .join("\n\n");
  return [
    `RASA ANALYSIS · GEO READINESS ${r.geo_readiness.toFixed(2)}/10 · ${r.verdict}`,
    `Domain: ${r.domain}`,
    `Engine: ${r.engine}`,
    `Model: ${r.model}`,
    `Seed: ${r.seed ?? "—"}`,
    "",
    dims,
    "",
    `Failure modes: ${r.failure_modes.join("; ") || "None"}`,
    `Priority fix: ${r.priority_fix}`,
    "",
    "RASA-Analyst · Nebula Personalization Tech Solutions Pvt. Ltd.",
    "Paper: DOI 10.5281/zenodo.20325460 · https://www.nebulatech.in",
    "GEO aid — not a claim about ChatGPT or Gemini ranking internals.",
  ].join("\n");
}

$("copy").addEventListener("click", async () => {
  if (!lastResult) return;
  await navigator.clipboard.writeText(reportText(lastResult));
  $("copy").textContent = "Copied";
  setTimeout(() => {
    $("copy").textContent = "Copy report";
  }, 1200);
});

$("download").addEventListener("click", () => {
  if (!lastResult) return;
  const blob = new Blob([JSON.stringify(lastResult, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `rasa-analysis-${lastResult.verdict.toLowerCase()}.json`;
  a.click();
});

$("run").addEventListener("click", async () => {
  if (!canScore) return;
  showError("");
  const btn = $("run");
  btn.disabled = true;
  btn.innerHTML = '<span class="spin">✦</span> Analyze →';
  document.body.classList.add("scoring");
  try {
    let res;
    if (activeTab === "url") {
      res = await fetch("/api/analyze-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: $("url").value }),
      });
    } else if (activeTab === "file") {
      const file = $("file").files[0];
      if (!file) throw new Error("Choose a file first.");
      const fd = new FormData();
      fd.append("file", file);
      res = await fetch("/api/analyze-file", { method: "POST", body: fd });
    } else {
      res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: $("content").value }),
      });
    }
    const data = await res.json();
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Analysis failed");
    render(data);
  } catch (e) {
    showError(e.message || String(e));
    if (!lastResult) $("idle").hidden = false;
  } finally {
    document.body.classList.remove("scoring");
    btn.disabled = !canScore;
    btn.innerHTML = "✦ Analyze →";
  }
});

health();
updateCount();
