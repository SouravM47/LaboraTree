# Laboratree — Testing & Demo Guide

How to exercise every Lab **properly**, with ready-made sample files, exact steps, expected
results, and the **intention** (what each thing proves).

Sample files live in `docs/samples/`. Small hand-made CSVs:
- `customers.csv` — has a **duplicate row** and a **missing value** (Signal / Insight / Decision)
- `sales_timeseries.csv` — 24 months, trend + seasonality (Trend)
- `leaky.csv` — a feature (`leak`) that **equals** the target `converted` (Leakage / Red-Team → FAIL)

Richer, realistic files — generate them once (the PDF/xlsx/docx are binary):
```powershell
cd apps/api; uv run --with fpdf2 python ../../docs/samples/make_sample_files.py
```
| File | For | Notes |
|---|---|---|
| `churn_clean.csv` | Model / Red-Team / Pipeline / Insight | classification, **no leakage** → red-team **PASS** (acc ≈ 0.7) |
| `housing.csv` | `model.ml.linear_regression` | regression, target `price` → **r² ≈ 0.92** |
| `campaign_timeseries.csv` | Trend `analyzer.causal_impact` | intervention at **index 10** → effect ≈ **+34 (14%)** |
| `survey_responses.csv` | Insight / Decision | `satisfaction`, `would_recommend`, `age_group` (subgroup) |
| `messy_finance.xlsx` | Signal | 2 sheets (revenue, costs) → consolidates to a master workbook |
| `quarterly_report.docx` | Signal | text + a table (extracted into the workbook) |
| `sample_paper_wine.pdf` | Paper Lab (Study + Experiment) | real text-layer PDF; mentions **wine** → auto-fetch works |
| `sample_paper.docx` | Paper Lab | `uv run python ../../docs/samples/make_sample_paper.py` (iris paper) |

**Tip:** drop `customers.csv` + `messy_finance.xlsx` + `quarterly_report.docx` **together** into Signal
Lab to see multi-format consolidation. Use `churn_clean.csv` for a clean Red-Team **PASS** to contrast
with `leaky.csv`'s **FAIL**. Upload `sample_paper_wine.pdf` to Paper Lab, then Experiment → it
auto-fetches the wine dataset.

---

## 0. Start everything

```powershell
docker compose -f infra/docker-compose.yml up -d postgres          # host port 5433
cd apps/api;  $env:POSTGRES_PORT="5433"; uv run uvicorn laboratree.main:app --reload --port 8001
cd apps/web;  npm run dev                                          # http://localhost:3000
cd apps/api;  $env:POSTGRES_PORT="5433"; uv run python -m laboratree.scripts.seed_demo
```
Set `apps/web/.env.local` → `NEXT_PUBLIC_API_URL=http://localhost:8001`, then **restart** `npm run dev`.

**Demo logins** (password `demo12345`): `owner@demo.lab`, `admin@demo.lab`, `analyst@demo.lab`, `viewer@demo.lab`.

### One-shot signal: run the whole test suite
```powershell
cd apps/api; $env:POSTGRES_PORT="5433"; uv run pytest      # expect: 65 passed, 1 skipped
```
**Intention:** proves every Lab + the trust layer, fully offline (LLM monkeypatched). The skip is the
Docker sandbox test.

### API auth (for the copy-paste examples below)
```powershell
$base="http://localhost:8001"
$t = Invoke-RestMethod $base/api/auth/login -Method Post -ContentType application/json `
     -Body (@{email="owner@demo.lab";password="demo12345"}|ConvertTo-Json)
$H = @{ Authorization="Bearer $($t.access_token)"; "X-Org-Id"=$t.org_id }
$pid = (Invoke-RestMethod $base/api/projects -Method Post -Headers $H -ContentType application/json `
        -Body (@{name="Demo"}|ConvertTo-Json)).id
```

---

## 1. Signal Lab — messy files → one master workbook
**Intention:** the front door; extract + reconcile any inputs, provenance-locked.
**UI:** open a project → **Signal Lab** → drop `customers.csv` (add a second file too if you like) →
**Consolidate**.
**Expect:** a Data Dictionary table (sheet, source, rows, cols) and a **Download .xlsx** button; the
master workbook has a `Data Dictionary` sheet.
**Example output:**
```json
{"run_id":"…","artifact_id":"…","download_url":"/api/artifacts/…/download",
 "summary":{"sources":["customers.csv"],"n_tables":1,"total_rows":10,"text_blocks":0,
   "sheets":[{"sheet":"customers","source":"customers.csv","kind":"csv","n_rows":10,"n_cols":5,
              "columns":"customer_id, tenure, monthly_charges, churn_score, segment"}],"errors":[]}}
```
**API:**
```powershell
curl.exe -s -X POST "$base/api/projects/$pid/signal/consolidate" `
  -H "Authorization: Bearer $($t.access_token)" -H "X-Org-Id: $($t.org_id)" `
  -F "files=@docs/samples/customers.csv;type=text/csv"
```

## 2. Insight Lab — EDA + charts
**Intention:** exploration where **every number is server-computed and Evidence-locked**.
**UI:** **Insight Lab** → drop `customers.csv` → **Profile** (see missing value on `monthly_charges`,
correlations) → build a **Histogram** (`tenure`), **Scatter** (`tenure` vs `monthly_charges`),
**Correlation heatmap**.
**Expect:** a profile table + a rendered Vega chart.
**Example output (profile, trimmed):**
```json
{"n_rows":10,"n_cols":5,"total_missing":1,
 "top_correlations":[{"a":"monthly_charges","b":"churn_score","corr":0.9507},
                     {"a":"tenure","b":"churn_score","corr":-0.8007}]}
```
**Example output (histogram spec, head):**
```json
{"mark":{"type":"bar","color":"#6DB33F"},
 "encoding":{"x":{"field":"tenure","bin":{"maxbins":30},"type":"quantitative"},
             "y":{"aggregate":"count","type":"quantitative","title":"count"}}}
```
**Break it:** heatmap needs ≥2 numeric columns — try a 1-column CSV → clear error, not a crash.

## 3. Trend Lab — decomposition
**Intention:** separate trend vs seasonality; causal-impact vs a counterfactual.
**UI:** **Trend Lab** → drop `sales_timeseries.csv` → value column `sales` → **Decompose**.
**Expect:** direction **up**, non-zero seasonality strength, a two-line (original vs trend) chart.
**Example output (summary):** `{"period":12,"direction":"up","seasonality_strength":0.6265}`
(plus `decomposition.{original,trend,seasonal,resid}` arrays for the chart).

## 4. Decision Lab — rules → actions
**Intention:** turn a score into recommended actions.
**UI:** **Decision Lab** → drop `customers.csv` → column `churn_score`, direction `≥`, threshold `0.5`
→ **Evaluate**.
**Expect / example output:**
```json
{"action_true":"act","action_false":"hold","n_true":5,"n_false":5,"rule":"churn_score >= 0.5"}
```
(5 rows have churn_score ≥ 0.5 — including the duplicated customer 2.)

## 5. Ideation Lab — Co-Scientist  *(uses real Azure)*
**Intention:** generate → debate (Elo) → evolve → synthesize hypotheses.
**UI:** **Ideation Lab** → goal e.g. *"How might we reduce customer churn for a telecom?"* →
**Run Co-Scientist**.
**Expect:** a ranked hypothesis list (Elo, rank, an "evolved" badge or two) + a research-direction
paragraph. Takes a few seconds / several model calls.
**Example output (shape):**
```json
{"goal":"reduce customer churn","hypotheses":[
   {"id":"h1","text":"Proactive discounts to high-risk customers cut churn","elo":1232.0,"rank":1,
    "critique":"testable; needs a control group","origin":"generated"},
   {"id":"e0","text":"Combine risk scoring with a loyalty program","elo":1216.0,"rank":2,"origin":"evolved"}],
 "meta_review":"The strongest direction couples churn-risk scoring with targeted retention offers …"}
```

## 6. Collection Lab — primary-research assist
**Intention:** AI complements the human on survey design / sampling.
**UI:** **Collection Lab** →
- **Sample size**: confidence 95%, margin 0.05 → **385** (instant, no LLM).
- **Questionnaire** *(Azure)*: goal "measure churn drivers", audience "telecom customers" → typed questions.
- **Bias check** *(Azure)*: paste `Don't you agree our service is excellent?` → flagged **leading**.
- **Synthetic pilot** *(Azure)*: persona "price-sensitive commuter" + a couple questions → simulated answers.
**API (no LLM):**
```powershell
Invoke-RestMethod $base/api/projects/$pid/collection/sample-size -Method Post -Headers $H `
  -ContentType application/json -Body (@{confidence=0.95;margin=0.05}|ConvertTo-Json)   # sample_size = 385
```
**Example outputs:**
```json
// sample-size
{"sample_size":385,"unadjusted":385,"params":{"confidence":0.95,"margin":0.05,"proportion":0.5,"z":1.96}}
// questionnaire
{"questions":[{"id":"q0","text":"How satisfied are you with our billing clarity?","type":"likert"}, …]}
// bias-check
{"findings":[{"question":"Don't you agree our service is excellent?","issue":"leading",
              "severity":"high","suggestion":"Ask neutrally: 'How would you rate our service?'"}]}
```

## 7. Paper Lab · Study  *(uses real Azure)*
**Intention:** understand any paper in plain language; chat grounded in it.
**Setup:** `cd apps/api; uv run python ../../docs/samples/make_sample_paper.py` (creates `sample_paper.docx`).
**UI:** **Paper Lab** → upload `sample_paper.docx` → **Generate Paper Card** → read fields (problem,
models, target, math-explained) → click **Explain simpler** → **chat**: *"What model does it use?"*
**Expect:** card says logistic regression / iris / species; chat answers with a `[0]` citation.
**Example output (Paper Card, trimmed):**
```json
{"status":"carded","card":{
  "problem_statement":"Classify iris flowers into three species from four measurements.",
  "models_used":["Logistic regression"],"target_variable":"species",
  "independent_variables":["sepal length","sepal width","petal length","petal width"],
  "math":[{"formula":"P(y=k|x)=softmax(Wx+b)","explanation":"Turns feature scores into class probabilities…"}],
  "results":"~0.95 accuracy on the held-out set."}}
// chat -> {"answer":"It uses logistic regression [0].","citations":[0]}
```

## 8. Paper Lab · Experiment  *(Azure + auto-fetch)*
**Intention:** reproduce and out-explore a paper; honest HITL when data can't be fetched.
**UI:** on the carded paper → **Experiment** tab → **Reproduce & Explore**.
**Expect:** a React Flow walkthrough; because the paper mentions **iris**, it's auto-fetched (sklearn
resolver). Click a **model** node → pick the iris dataset → **Run node** → metrics shown next to the
paper's reported result. **Fork** to a different model and compare.
**HITL case:** if a dataset can't be fetched, you'll see an **upload** slot with guidance — upload any
CSV to resolve it and the experiment flips to **ready**.
**Example output (experiment, trimmed):**
```json
{"status":"ready","walkthrough":[{"id":"n0","kind":"data","title":"Load data"},
   {"id":"n3","kind":"model","title":"Logistic regression","component_id":"model.ml.logistic_regression"}],
 "fetch_report":{"fetched":[{"name":"iris","dataset_id":"…","resolver":"sklearn_toy","n_rows":150,"n_cols":5}],
                 "unresolved":[]}}
// run a node -> {"metrics":{"accuracy":0.947,"f1_macro":0.946},"paper_reported":"~0.95 accuracy…","forked":false}
```

## 9. Pipeline — chain Labs end to end
**Intention:** the dataset flows step→step; each is a tracked, provenance-locked run.
**UI:** **Pipeline** → drop `customers.csv` → add `transform.drop_duplicates` →
`transform.mean_impute` → `analyzer.eda_profile` → **Run pipeline**.
**Expect:** the React Flow chain turns **green**; step 1 shows `n_rows: 9` (a dup removed); each step
has a **🔒 provenance** chip — click it to see the manifest + Evidence.
**Example output (trimmed):**
```json
{"ok":true,"n_rows_final":9,"steps":[
  {"component_id":"transform.drop_duplicates","status":"succeeded","evidence_count":1,
   "preview":{"dataset":{"n_rows":9}}},
  {"component_id":"analyzer.eda_profile","status":"succeeded",
   "preview":{"profile":{"n_rows":9,"n_cols":5,"total_missing":1}}}]}
```
**API:**
```powershell
Invoke-RestMethod $base/api/projects/$pid/pipeline/run -Method Post -Headers $H -ContentType application/json -Body (@{
  dataset=@(@{a=1;b=2.0},@{a=1;b=2.0},@{a=2;b=$null});
  steps=@(@{component_id="transform.drop_duplicates";params=@{}},@{component_id="analyzer.eda_profile";params=@{}})
}|ConvertTo-Json -Depth 6)
```

## 10. Report card — the trustworthy output
**Intention:** every figure bound to a re-runnable execution + a trust score.
**UI:** after running a few things, project header → **Report card** → opens a branded HTML report with
a **trust score** and per-result provenance lines.
**Example output (POST /report):**
```json
{"run_id":"…","artifact_id":"…","download_url":"/api/artifacts/…/download","project":"Demo",
 "trust":{"score":100,"reproducibility":1.0,"evidence_coverage":1.0,"leakage_flags":0,"n_runs":3}}
```
(The downloaded HTML shows each run's metrics with a `🔒 run · code · data · seed` line.)

---

## 11. The four differentiators — prove them directly

**Leakage Sentinel** — run on `leaky.csv` (`leak` == `converted`):
```powershell
$rows = (Import-Csv docs/samples/leaky.csv | ForEach-Object {
  @{age=[int]$_.age; income=[int]$_.income; leak=[int]$_.leak; converted=[int]$_.converted} })
Invoke-RestMethod $base/api/projects/$pid/runs -Method Post -Headers $H -ContentType application/json `
  -Body (@{component_id="analyzer.leakage_sentinel"; params=@{target="converted"}; dataset=$rows}|ConvertTo-Json -Depth 6)
```
**Expect / example output:**
```json
{"findings":[{"check":"target_leakage","severity":"high","column":"leak",
              "detail":"'leak' is identical to target 'converted'"}]}
```
**Intention:** catches inflated/fake results.

**Red-Team Critic** — same `leaky.csv`, component `critic.red_team`, `params={target="converted"}`.
**Expect / example output:**
```json
{"verdict":"FAIL","base_metric":1.0,"robustness_drop":0.0,
 "findings":[{"check":"leakage","severity":"high","detail":"target/temporal leakage detected"}]}
```
Run it on clean data (e.g. iris target) → `{"verdict":"PASS", …}`.
**Intention:** an independent adversary gates weak models.

**Provenance** — click **🔒 provenance** on any Pipeline step (manifest: seed/data/code + Evidence).
**Reproducibility** — every run carries a `repro_manifest`; identical inputs re-run deterministically.

---

## 12. RBAC / Team
Log in as **viewer@demo.lab** → try to create a project → **403** (read-only). As **owner/admin** →
**Team** tab → add a member (must be registered) / change roles. **Intention:** multi-tenant, role-gated.

---

## Gotchas
- **Ports:** if `8000` is taken, run the API on `8001` and set `apps/web/.env.local` to match, then
  **restart** `npm run dev` (NEXT_PUBLIC_* loads only at startup).
- **Never run `npm run build` while `npm run dev` is live** — it corrupts `.next`. Use `npx tsc --noEmit`.
- **Azure-backed features** (Ideation, Collection LLM tools, Paper Card/chat, Experiment ref-extraction)
  make real model calls; the automated tests mock these so `pytest` stays offline.
