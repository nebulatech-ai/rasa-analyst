# Locked eval

Fixed snippets and expected **gates** (domain, verdict band, RP cap, forbidden failure modes). Do not copy a live 8.80 into gold.

```text
.venv\Scripts\python.exe -m eval.run
.venv\Scripts\python.exe -m eval.run --repeats 3
```

`--repeats 3` flags dimension jitter ≥ 2 on the same case.

If a case is wrong, change the gold in a reviewed edit. Do not “fix” gold by pasting the model’s last JSON.
