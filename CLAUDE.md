# CLAUDE.md — Real-Time Anomaly Detection System

## 1. Project Overview
A real-time anomaly detection pipeline that ingests a streaming time-series, engineers rolling-window features, scores each point with three models (Isolation Forest, Prophet, LSTM Autoencoder), combines them via a weighted ensemble with adaptive thresholding, serves predictions through FastAPI, tracks experiments in MLflow, and visualizes results in a Streamlit dashboard. Built as a 2-day, portfolio-grade reference implementation. See `PRD.md` for full requirements.

## 2. Tech Stack
- **Language**: Python 3.11
- **ML/Stats**: scikit-learn (Isolation Forest), Prophet, PyTorch (LSTM Autoencoder), NumPy, pandas, SciPy (FFT)
- **Feature store**: Redis (optional) or in-memory dict
- **API**: FastAPI + Pydantic + Uvicorn
- **Tracking**: MLflow
- **Dashboard**: Streamlit
- **Testing**: pytest
- **Containerization**: Docker, docker-compose
- **Notebook**: Jupyter (EDA only — not part of the served system)

## 3. Folder Structure
```
anomaly-detection-system/
├── data/
│   ├── ingest.py          # CSV stream reader + Kafka stub
│   ├── datasets/           # NAB .csv files
│   └── stream_sim.py       # synthetic stream generator
├── features/
│   ├── engineer.py         # rolling stats, z-score, lag, FFT
│   └── store.py            # Redis or in-memory feature cache
├── models/
│   ├── isolation_forest.py
│   ├── prophet_model.py
│   ├── lstm_autoencoder.py
│   └── ensemble.py         # scorer + adaptive threshold
├── api/
│   ├── main.py              # FastAPI app
│   ├── schemas.py           # Pydantic request/response models
│   └── middleware.py        # request logging, latency tracking
├── tracking/
│   └── mlflow_utils.py      # experiment logging helpers
├── dashboard/
│   └── app.py               # Streamlit UI
├── tests/
│   ├── test_features.py
│   ├── test_models.py
│   └── test_api.py
├── notebooks/
│   └── EDA.ipynb
├── Dockerfile.api
├── Dockerfile.dashboard
├── docker-compose.yml
├── requirements.txt
├── README.md
├── PRD.md
└── CLAUDE.md
```
Do not add new top-level directories without updating this section.

## 4. Build Commands
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
docker-compose build          # build all service images
docker-compose up             # run API + dashboard (+ redis if enabled)
```

## 5. Test Commands
```bash
pytest                              # run full suite
pytest tests/test_features.py -v    # feature engineering unit tests
pytest tests/test_models.py -v      # model-level tests
pytest tests/test_api.py -v         # API contract tests
python -m scripts.latency_bench     # 1000-request latency benchmark (p50/p95/p99)
```
A model or feature change is not done until its corresponding test file passes.

## 6. Coding Style
- Follow PEP 8; format with `black` and lint with `ruff` before committing.
- Type hints are required on all function signatures in `features/`, `models/`, and `api/`.
- Docstrings (Google style) required on every public class and function — explain *what* it does and *why*, not a restatement of the signature.
- Prefer small, composable functions over long monolithic methods, especially in `engineer.py` and `ensemble.py`.
- No bare `except:` clauses — catch specific exceptions and log context.

## 7. Naming Conventions
- Modules: `snake_case.py`.
- Classes: `PascalCase` (e.g., `FeatureEngineer`, `IFModel`, `ProphetModel`, `LSTMAETrainer`, `EnsembleScorer`).
- Functions/variables: `snake_case`.
- Constants: `UPPER_SNAKE_CASE` (e.g., `SEQ_LEN`, `DEFAULT_THRESHOLD`).
- Feature store keys: `{series_id}:{timestamp}` — do not deviate from this pattern.
- Test files mirror source files: `models/isolation_forest.py` → `tests/test_models.py::test_isolation_forest_*`.

## 8. Architecture Rules
- Every model (`isolation_forest.py`, `prophet_model.py`, `lstm_autoencoder.py`) must expose a consistent interface: `.fit(X)` and `.score(X) -> float | np.ndarray`. This is required so `ensemble.py` can treat all three interchangeably.
- `EnsembleScorer` must never call a model's internal training logic — it only consumes `.score()` outputs.
- Feature engineering must happen once per point and be cached in the feature store; models must not recompute features independently.
- The API layer (`api/`) must not contain model logic — it imports from `models/` and `features/` only. Keep `main.py` thin.
- LSTM inference inside the API path must always run inside `torch.no_grad()`.
- The dashboard (`dashboard/app.py`) must read from the API or the alert log — it must never import model classes directly or duplicate scoring logic.
- Kafka stub in `ingest.py` must conform to the same interface as the CSV reader so swapping in a real broker later requires no changes elsewhere.

## 9. Libraries Allowed
- `scikit-learn`, `prophet`, `torch`, `numpy`, `pandas`, `scipy`
- `fastapi`, `pydantic`, `uvicorn`
- `mlflow`
- `streamlit`
- `redis` (optional, behind a feature flag in `store.py`)
- `pytest`, `httpx` (for API testing)
- `black`, `ruff` (dev-only, not a runtime dependency)

## 10. Libraries Forbidden
- No additional web frameworks (Flask, Django) — FastAPI only.
- No alternative experiment trackers (Weights & Biases, Neptune) — MLflow only, per PRD scope.
- No ORMs or relational DB drivers (SQLAlchemy, psycopg2) — no relational DB is in scope for v1 (see PRD Section 12).
- No async task queues (Celery, RQ) — out of scope for this build.
- No real Kafka client libraries (`kafka-python`, `confluent-kafka`) until "real Kafka integration" future-scope work is explicitly approved — the stub must remain dependency-free.
- No cloud SDKs (boto3, google-cloud-*) — this is a local/Docker-only deployment.

## 11. Git Workflow
- Commit messages follow Conventional Commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`.
- Day 1 checkpoint commit message: `feat: data pipeline + three models trained` (per schedule).
- One logical change per commit; do not bundle unrelated feature + model changes.
- Run `pytest` and `black --check .` before every commit — do not commit failing tests or unformatted code.
- No direct commits of files under `data/datasets/` (NAB CSVs) or trained model artifacts — these belong in `.gitignore` unless explicitly tracked via MLflow's artifact store.
- Branch naming: `feature/<short-name>`, `fix/<short-name>` if working beyond a single-branch flow.

## 12. Security Rules
- Never commit API keys, Redis credentials, or `.env` files — use `.env.example` as the template and add `.env` to `.gitignore`.
- Validate all `/predict` input via Pydantic schemas — never trust raw request bodies.
- Do not log raw request payloads containing sensitive values at INFO level in production-style runs; latency middleware should log timing and status, not full payloads, by default.
- Pin all dependency versions in `requirements.txt` — no unpinned installs.
- Docker images must not run as root where avoidable; expose only the ports declared in the Dockerfile (8000 for API).

## 13. Testing Requirements
- `test_features.py` must cover: z-score of a constant series equals 0, z-score of an injected outlier exceeds 3, warm-up period (insufficient history) returns `None` rather than raising, FFT peak output is non-negative.
- `test_models.py` must cover: each model's `.fit()`/`.score()` interface returns expected shapes/types, and a sanity check that injected anomalies score higher than normal points.
- `test_api.py` must cover: valid `/predict` request returns 200 with expected schema, malformed request returns 422, `/health` returns 200 with `models_loaded` populated.
- All new features or models require corresponding tests before being considered complete — no exceptions.
- Latency benchmark (1000 requests, p50/p95/p99) must be re-run after any change to `models/` or `api/` that could affect inference time.

## 14. Documentation Rules
- `README.md` must follow the structure in PRD Section 17: description → dashboard screenshot/GIF → metrics table → architecture diagram → install steps → API reference → future work.
- Every public class/function needs a docstring (see Section 6).
- Any architecture decision that deviates from `PRD.md` must be noted inline in code comments and reflected back into `PRD.md` — the PRD is the source of truth and should not silently drift from the implementation.
- MLflow run names/tags must be descriptive enough to identify model type and key hyperparameters without opening the run.

## 15. Output Formatting Rules
- API responses are JSON only, matching the schemas defined in `api/schemas.py` (see PRD Section 13) — do not add undocumented fields without updating both `schemas.py` and `PRD.md`.
- Logs use structured logging (key=value or JSON), not free-form print statements, in `api/` and `models/`.
- Dashboard numeric displays (scores, latency) should be rounded to 3 decimal places for readability.
- Notebook outputs in `EDA.ipynb` should be cleared before commit unless the output is the explicit deliverable (e.g., a plot referenced in the README).

## 16. Common Commands
```bash
python data/stream_sim.py                      # generate synthetic stream
python -m models.isolation_forest --train       # train Isolation Forest
python -m models.prophet_model --train          # train Prophet
python -m models.lstm_autoencoder --train       # train LSTM AE (20 epochs)
python -m models.ensemble --tune                # grid-search ensemble weights
uvicorn api.main:app --reload --port 8000       # run API locally
streamlit run dashboard/app.py                  # run dashboard locally
mlflow ui                                       # view experiment tracking UI
curl -X POST localhost:8000/predict -d '{"timestamp":"2026-06-30T10:00:00Z","value":12.5}'
```

## 17. Known Pitfalls
- Forgetting `torch.no_grad()` in the LSTM inference path is the most common cause of latency benchmark failures (p99 > 50ms) — check this first if the benchmark regresses.
- Rolling-window z-score divides by std; a flat/constant signal during warm-up produces division-by-zero — must be guarded, not just hoped around.
- NAB's ~2% anomaly rate means accuracy is a misleading metric — always evaluate with precision/recall/F1, never lead with accuracy in logs or README.
- Prophet's confidence interval width directly trades off false positives vs. missed anomalies — do not tune this "by eye"; tune against validation F1.
- Redis being unavailable should not crash the pipeline silently — `store.py` must explicitly log a fallback to in-memory mode, not fail silently in a way that masks a real outage in a real deployment.
- Ensemble weights tuned only on validation data can overfit — always report final metrics on the untouched test split.
- Out-of-order timestamps arriving at the API can corrupt rolling-window state if not explicitly handled — see PRD Section 15 (Edge Cases).

## 18. Important Files
- `PRD.md` — source of truth for requirements, scope, and acceptance criteria.
- `models/ensemble.py` — the central design artifact of the project; most interview questions trace back to this file.
- `features/engineer.py` — shared dependency for every model; bugs here silently corrupt all three models' inputs.
- `api/main.py` — the production-facing entry point; latency and correctness here are directly tested by acceptance criteria.
- `dashboard/app.py` — the primary demo surface; this is what a reviewer sees first.
- `tests/test_features.py`, `tests/test_models.py`, `tests/test_api.py` — must stay green; CI/manual review treats these as gating.
- `docker-compose.yml` — defines the entire runnable system; must be kept in sync with any new service added to `api/` or `dashboard/`.
