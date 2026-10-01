# PITWALL: F1 fan hub + analyst dashboard

A full-stack Formula 1 project built on the Ergast/Jolpica dataset (1950–2024) and the four notebooks
in `notebooks/` (Naïve Bayes, classification, regression, K-Means, visualisation).

| Who | What they get |
|---|---|
| **Fans** (register / log in / Google) | An **About F1** explainer (race weekend, points, the car with video, flags, glossary, history). **Drivers** and **Constructors** pages: all 861 drivers and 211 teams with filters, search, sort, championship standings for any season, and short wiki-style profiles with charts. **Profile**: choose favourite drivers and teams, sessions and Grands Prix to follow. **My Feed**: next race countdown, upcoming sessions in your timezone, live standings, latest result, all filtered to your picks. |
| **Analyst (admin)** at `/admin/login` | A clean, professional dashboard with a global season-range filter. Analysis pages: Overview, Driver comparison (incl. team-mate head-to-head), Constructor comparison, Race analysis (lap chart, gaps, lap times, pit stops, qualifying), Qualifying, Pit stops, Reliability, Circuits (map). Model pages: Points-finish classifier with what-if predictor, Race-winner classifier with grid scenario, Fastest-lap regression, Driver clustering with K and feature controls. |

## Run it (one command)

Requirements: **Python 3.10+**. Node is *not* needed; the built frontend is included in `frontend/dist`.

```bash
# Windows
start.bat

# macOS / Linux
./start.sh
```

Or manually:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r backend/requirements.txt
python run.py
```

Open **http://localhost:8000**.

* Fan site: register a new account, or use Google once configured.
* Analyst dashboard: **http://localhost:8000/admin/login**. Default login is `admin@pitwall.local` / `Admin@123`.
  Change it in `.env` before sharing the app.

On the very first start the three supervised models train in the background (~20 s). The model pages show a
"training" message and refresh on their own. After that they are cached in `backend/models_cache.joblib`.

## Configuration (`.env`)

Copy `.env.example` to `.env`:

| Variable | Purpose |
|---|---|
| `SUPABASE_URL`, `SUPABASE_KEY` | Supabase Cloud Database credentials for storing users and preferences (falls back to local SQLite `pitwall.db` if empty). |
| `GOOGLE_CLIENT_ID` | Turns on “Continue with Google”. |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | The analyst account created on start-up. |
| `JWT_SECRET` | Session signing key (auto-generated if empty). |
| `PORT` | Defaults to 8000. |

### Setting up Supabase (Storing Users & Preferences)

1. Create a free project at [supabase.com](https://supabase.com).
2. In the Supabase Dashboard, open **SQL Editor** -> **New Query**, paste the contents of [`supabase_schema.sql`](supabase_schema.sql), and click **Run**.
3. Go to **Project Settings -> API** and copy:
   - **Project URL** (`https://<project-ref>.supabase.co`)
   - **anon** public key or **service_role** secret key
4. Add them to your `.env`:
   ```env
   SUPABASE_URL=https://<your-project-ref>.supabase.co
   SUPABASE_KEY=<your-key>
   ```
5. Test the connection:
   ```bash
   python backend/test_supabase.py
   ```
6. (Optional) Migrate existing local SQLite users and preferences to Supabase:
   ```bash
   python backend/migrate_to_supabase.py
   ```

### Setting up Google sign-in

1. Go to Google Cloud Console → **APIs & Services → Credentials → Create credentials → OAuth client ID**.
   (Configure the OAuth consent screen first if asked: External, add your email as a test user.)
2. Application type: **Web application**.
3. **Authorized JavaScript origins**: `http://localhost:8000` (add `http://localhost:5173` if you use dev mode).
4. Copy the client ID (`xxxx.apps.googleusercontent.com`) into `.env` as `GOOGLE_CLIENT_ID=...` and restart.

The browser gets a Google ID token; the backend verifies it with `google-auth` and creates or signs in the user.

## Live season data

The CSV dataset ends with the 2024 season. The **feed** and the profile pickers fetch the current calendar,
standings and last result from the free **Jolpica-F1 API** (`api.jolpi.ca`, the successor of Ergast),
cached for 30 minutes. If the API can’t be reached, the app falls back to the 2024 season from the dataset and says so.

## Media (images and videos)

All media links live in `frontend/src/media.js`:

* **Hero background video:** drop an MP4 at `frontend/dist/media/hero.mp4` (or `frontend/public/media/hero.mp4`
  before a rebuild) and it is used automatically. Otherwise a muted YouTube onboard lap plays.
* **Car explainer video:** “How A Formula 1 Car is Made” (YouTube `kV2fo40nIHs`), plus a link to
  “How It’s Made: Formula 1 Cars” (`CktpA3To7T4`).
* **Images:** Creative-Commons photos from Wikimedia Commons. Replace them with your own if you like.

The design uses an F1-inspired palette (carbon black, racing red, Titillium Web) but no official Formula 1 logos or trademarks.

## Developing the frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to the Python server on :8000
npm run build      # writes frontend/dist, which run.py serves
```

Stack: React 18 + Vite + React Router + Plotly (charts). Backend: FastAPI, pandas, scikit-learn, SQLite, JWT.

## Project layout

```
run.py                     start script (loads .env, serves API + built frontend)
backend/
  app/main.py              FastAPI app, static SPA hosting
  app/auth.py              register / login / Google / admin login, JWT, PBKDF2 password hashing
  app/db.py                SQLite users + preferences (backend/pitwall.db)
  app/data.py              loads the CSVs, career + season aggregates, standings
  app/live.py              Jolpica-F1 client with cache
  app/routes_fan.py        drivers, constructors, standings, schedule, catalog, profile, feed
  app/routes_admin.py      analyst endpoints (overview, compare, race, quali, pits, reliability, circuits, models)
  app/ml.py                models ported from the notebooks
  data/                    the 15 CSV files
frontend/src/
  fan/                     login, register, about, drivers, constructors, feed, profile
  admin/                   admin shell + pages/
notebooks/                 the original notebooks
```

## Models (from the notebooks)

| Page | Notebook | Setup | Test result |
|---|---|---|---|
| Points-finish classifier | `f1_naive_bayes_classification.ipynb` | GaussianNB, PowerTransform + `var_smoothing` grid search, RF benchmark; features grid, driver/team form (last 10), round, season, circuit geo; 80/20 stratified | ≈ 76% accuracy (baseline 52%), AUC ≈ 0.84 |
| Race-winner classifier | `f1_classification_project.ipynb` | One row per race, per-team best grid / recent wins & podiums / circuit wins; DT, NB, RF; train 2000–2017, test 2018–2024 | RF ≈ 58% accuracy over 10 classes |
| Fastest-lap regression | `f1_regression_project.ipynb` | Linear, Ridge, RF, Gradient Boosting; train 2004–2020, test 2021–2024 | Ridge best, R² ≈ 0.82, RMSE ≈ 8.4 km/h |
| Driver clustering | `clustering.ipynb` | K-Means on standardised driver-season features; live controls for K, seasons, min races, features | silhouette ≈ 0.47 at K=4 (2004–2024) |

One difference from the regression notebook: rows without an official fastest-lap speed are dropped instead of imputed.

Fan-made educational project. Not affiliated with Formula 1, the FIA or any team.
