# TMS Backend API

Backend for the Transportation Management System (TMS). It is a FastAPI service that stores shops, depots, fleets, vehicles, orders, and routing constraints in MySQL (SQLite when `DATABASE_URL` is unset), builds a road distance and duration matrix with OSRM, and solves delivery routes with Google OR-Tools.

`main.py` only starts the server. The application is created in `src/api/app.py`.

## What it does

- CRUD for shops, depots, fleets, vehicles, orders, order groups, and routing constraints
- Vehicle routing that minimizes distance or time, then stores the result as a job
- Distance and duration matrix sync for shops marked `to_create` or `to_update`
- A static operations UI served at `/` from the `ui/` folder

## Tech stack

- Python 3.11+
- FastAPI, Pydantic, Uvicorn
- SQLAlchemy 2
- Google OR-Tools
- OSRM for road distance and duration
- MySQL (`mysql+pymysql`) or SQLite
- `uv` for the environment and lockfile

## Project structure

```text
TMS-Backend/
├── main.py                      # process entrypoint; imports src.api.app:app
├── pyproject.toml
├── .env.example
├── ui/                          # static UI, mounted at /
├── scripts/                     # matrix sync and CSV ingest
├── tests/
└── src/
    ├── api/
    │   ├── app.py               # FastAPI app, CORS, table create, routers, UI
    │   ├── deps.py
    │   └── routes/              # one package per resource
    │       ├── shops/
    │       ├── depots/
    │       ├── fleets/
    │       ├── vehicles/
    │       ├── vehicle_constraints/
    │       ├── geo_constraints/
    │       ├── predefined_routes/
    │       ├── orders/
    │       ├── order_groups/
    │       ├── jobs/
    │       ├── optimization/
    │       └── matrix/
    ├── infrastructure/
    │   ├── config.py            # paths and settings from .env
    │   ├── logging.py
    │   ├── exceptions.py
    │   └── database/            # engine, session, ORM models
    ├── matrix/                  # OSRM client and distance-matrix manager
    └── vrp/                     # OR-Tools model, solver, and map output
```

Each route package is a vertical slice: `endpoints.py` (HTTP), `repository.py` (queries), and `schemas.py` (request and response models).

On startup, `src/api/app.py` loads configuration, creates missing data directories, creates tables with `models.Base.metadata.create_all`, registers the routers, and mounts `ui/` at `/`.

## API

Interactive docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Operations UI: `http://127.0.0.1:8000/`

| Area | Prefix | Notes |
|---|---|---|
| Customers | `/location/customer` | Customer location records |
| Depots | `/location/depot` | Depot location records |
| Fleets | `/fleet` | |
| Vehicles | `/vehicle` | Create under `POST /vehicle/{fleet_id}` |
| Vehicle constraints | `/vehicle-constraint` | `PUT /vehicle-constraint/{vehicle_id}` |
| Geo constraints | `/geo-constraint` | Includes `/by-vehicle/{vehicle_id}` |
| Predefined routes | `/predefined-route` | |
| Orders | `/order` | |
| Order groups | `/order-group` | |
| Optimization | `/optimize` | `POST /optimize/` starts a routing job |
| Jobs | `/job` | Job status, vehicle routes, complete, cancel |
| Matrix | `/matrix` | `GET /stats`, `GET /pending`, `POST /sync` |

`POST /matrix/sync` runs in the background. It reads GPS rows whose `matrix_status` is `to_create` or `to_update`, asks OSRM for each missing pair, and marks those rows `updated`.

`POST /optimize/` expects at least one vehicle and one order id. The solver runs in the background and writes a job that `/job` can read.

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- MySQL 8, if you use the `DATABASE_URL` in `.env.example`. Without `DATABASE_URL`, the app uses a SQLite file under `data/<CLIENT>/outputs/database/`.

## Setup

```powershell
uv sync --extra test
copy .env.example .env
```

Edit `.env` before the first run. The example URL is a local MySQL database named `delivery_db`:

```text
DATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/delivery_db
```

Create that database (or point `DATABASE_URL` at one that already exists) before starting the app. Tables are created on startup.

## Configuration

Settings are read in `src/infrastructure/config.py`. Copy `.env.example` to `.env`.

| Variable | Role | Default if unset |
|---|---|---|
| `CLIENT` | Subfolder under `data/` | `common` |
| `DATA_FOLDER` | Root data directory | `data` |
| `MASTER_FOLDER` | GPS and matrix files for the client | `master` |
| `MASTER_GPS` | Shop GPS filename | `master_gps.csv` |
| `DISTANCE_MATRIX` | Distance matrix filename | `distance_matrix.csv` |
| `DURATION_MATRIX` | Duration matrix filename | `duration_matrix.csv` |
| `OUTPUT_FOLDER` | Solver and map output | `outputs` |
| `DATABASE_FOLDER` | SQLite directory, used when `DATABASE_URL` is unset | `database` |
| `DATABASE_URL` | SQLAlchemy URL | SQLite file for `CLIENT` |
| `HOST` | Uvicorn bind host (`python main.py`) | `0.0.0.0` |
| `PORT` | Uvicorn bind port (`python main.py`) | `8000` |
| `RELOAD` | Auto-reload when using `python main.py` | `false` |
| `API_PUBLIC_URL` | Browser API origin; leave empty for same-origin UI | _(empty)_ |
| `SOLVER_TIME_LIMIT_SECONDS` | OR-Tools time limit | `30` |
| `OSRM_BASE_URL` | OSRM route service | `http://router.project-osrm.org/route/v1/car` |

Resolved paths look like `data/common/master/` and `data/common/outputs/`. The app creates these directories on startup. Logs go to `logs/`.

The UI loads `/runtime-config.js` then uses relative API paths by default, so changing `HOST`/`PORT` (or hosting behind a reverse proxy) does not require editing JS. Set `API_PUBLIC_URL` only if the UI is hosted on a different origin than the API.

## Run

```powershell
uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Or (uses `HOST` / `PORT` / `RELOAD` from `.env`):

```powershell
uv run python main.py
```

## Tests

```powershell
uv run pytest
```

Coverage is split by area: shops and depots, fleets and vehicles, orders and groups, routing constraints, and jobs and optimization. Tests use the `test` extra (`pytest`, `httpx`).

## Scripts

From the project root, with the virtual environment active:

```powershell
uv run python scripts/update_matrix.py
uv run python scripts/ingest_from_csv.py --dry-run
```

`scripts/update_matrix.py` processes pending matrix rows through OSRM. `scripts/ingest_from_csv.py` loads shop and matrix CSVs straight into the database. Run it with `--dry-run` first. `scripts/fix_matrix_status.py` repairs `matrix_status` values.

## Development notes

- CORS allows every origin. That is for local development.
- ORM models live in `src/infrastructure/database/models.py`. Changing a model does not alter an existing table; `create_all` only creates missing tables.
- Route handlers stay thin. Query logic belongs in the resource `repository.py`. Solver and matrix code belong in `src/vrp` and `src/matrix`.
