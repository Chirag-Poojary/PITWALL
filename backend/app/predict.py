"""Driver-level race-winner prediction for the next Grand Prix.

The admin "Race-winner classifier" (ml.train_winner) works on constructors and on
grids that only exist after qualifying. For the fan feed we need something that
can run on live data: a per-driver model that scores every entrant of the next race
from information known beforehand, then normalises the scores into win and podium
probabilities across the field.

History = the CSV warehouse (1950–2024) + every season since then pulled from the
Jolpica-F1 API, so the same feature code serves training and live prediction.

Two variants are trained:
  * "pre"  – before qualifying (form, team form, circuit history)
  * "grid" – after qualifying, adding the qualifying position as the grid slot
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import live
from .data import clean, get_data

RS = 42
FIRST_SEASON, TEST_FROM = 2000, 2021
PRE = ["d_avg_finish_5", "d_win_rate_10", "d_podium_rate_10", "d_top10_rate_10", "d_dnf_rate_10", "d_starts",
       "c_best_5", "c_win_rate_10", "c_podium_rate_10", "d_circ_avg", "d_circ_wins", "form_rank", "team_rank", "field"]
GRID = PRE + ["grid"]
FEATURE_LABELS = {
    "d_avg_finish_5": "Driver's average finish, last 5 races", "d_win_rate_10": "Driver's wins, last 10 races",
    "d_podium_rate_10": "Driver's podiums, last 10 races", "d_top10_rate_10": "Driver's points finishes, last 10",
    "d_dnf_rate_10": "Driver's retirements, last 10", "d_starts": "Career starts",
    "c_best_5": "Team's best finish, last 5 races", "c_win_rate_10": "Team's wins, last 10 races",
    "c_podium_rate_10": "Team's podiums, last 10 races", "d_circ_avg": "Driver's average finish at this circuit",
    "d_circ_wins": "Driver's wins at this circuit", "form_rank": "Driver form rank in the field",
    "team_rank": "Team form rank in the field", "field": "Number of starters", "grid": "Grid / qualifying position",
}


# ---------------------------------------------------------------- history
def dataset_history() -> pd.DataFrame:
    d = get_data()
    circ = d.circuits.set_index("circuitId")["circuitRef"]
    r = d.res
    h = pd.DataFrame({
        "date": pd.to_datetime(r["date"]), "season": r["year"].astype(int), "round": r["round"].astype(int),
        "circuit": r["circuitId"].map(circ), "driver": r["driverRef"], "driver_name": r["driver_name"],
        "code": r["code"], "team": r["constructorRef"], "team_name": r["constructor_name"],
        "grid": r["grid"].where(r["grid"] > 0), "pos": r["positionOrder"].astype(float), "dnf": r["dnf"].astype(float),
    })
    return h[h["season"] >= FIRST_SEASON - 2]  # two seasons of warm-up for the rolling windows


def live_history(through_season: int) -> tuple[pd.DataFrame, list[int]]:
    """Seasons after the CSV dataset (2025 onwards) from the live API."""
    frames, got = [], []
    last = get_data().latest_season
    for y in range(last + 1, through_season + 1):
        rows = live.season_results(y, finished_season=y < through_season)
        if rows is None:
            raise RuntimeError(f"Live results for {y} unavailable")
        if rows:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df["pos"] = df["pos"].astype(float)
            df["dnf"] = (~df["status"].str.match(r"^(Finished|\+\d+ Laps?|Lapped)$")).astype(float)
            frames.append(df.drop(columns=["status", "race_name"]))
            got.append(y)
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), got


# ---------------------------------------------------------------- features
def build_features(h: pd.DataFrame) -> pd.DataFrame:
    """Pre-race features for every row. Rows with pos = NaN are races still to come."""
    h = h.copy()
    h["race"] = h["season"].astype(str) + "-" + h["round"].astype(int).astype(str).str.zfill(2)
    h = h.sort_values(["date", "race", "driver"]).reset_index(drop=True)
    h["win"] = (h["pos"] == 1).astype(float).where(h["pos"].notna())
    h["podium"] = (h["pos"] <= 3).astype(float).where(h["pos"].notna())
    h["top10"] = (h["pos"] <= 10).astype(float).where(h["pos"].notna())
    h["dnf"] = h["dnf"].where(h["pos"].notna())

    gd = h.groupby("driver", sort=False)

    def roll(col, n):
        return gd[col].transform(lambda s: s.shift(1).rolling(n, min_periods=1).mean())

    h["d_avg_finish_5"] = roll("pos", 5)
    h["d_win_rate_10"] = roll("win", 10)
    h["d_podium_rate_10"] = roll("podium", 10)
    h["d_top10_rate_10"] = roll("top10", 10)
    h["d_dnf_rate_10"] = roll("dnf", 10)
    h["d_starts"] = gd.cumcount().clip(upper=300)

    gc = h.groupby(["driver", "circuit"], sort=False)
    h["d_circ_avg"] = gc["pos"].transform(lambda s: s.shift(1).expanding().mean())
    h["d_circ_wins"] = gc["win"].transform(lambda s: s.shift(1).fillna(0).cumsum())

    # team: best car per race, rolled over the team's races
    t = (h.groupby(["team", "race", "date"], sort=False)["pos"].min().reset_index()
         .sort_values(["date", "race"]))
    t["t_win"] = (t["pos"] == 1).astype(float).where(t["pos"].notna())
    t["t_pod"] = (t["pos"] <= 3).astype(float).where(t["pos"].notna())
    gt = t.groupby("team", sort=False)
    t["c_best_5"] = gt["pos"].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    t["c_win_rate_10"] = gt["t_win"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    t["c_podium_rate_10"] = gt["t_pod"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    h = h.merge(t[["team", "race", "c_best_5", "c_win_rate_10", "c_podium_rate_10"]], on=["team", "race"], how="left")

    # sensible values for rookies and new teams (same rule in training and live use)
    h["d_avg_finish_5"] = h["d_avg_finish_5"].fillna(15.0)
    for c in ["d_win_rate_10", "d_podium_rate_10", "d_top10_rate_10", "c_win_rate_10", "c_podium_rate_10", "d_circ_wins"]:
        h[c] = h[c].fillna(0.0)
    h["d_dnf_rate_10"] = h["d_dnf_rate_10"].fillna(0.2)
    h["c_best_5"] = h["c_best_5"].fillna(12.0)
    h["d_circ_avg"] = h["d_circ_avg"].fillna(h["d_avg_finish_5"])

    gr = h.groupby("race", sort=False)
    h["field"] = gr["driver"].transform("size")
    h["form_rank"] = gr["d_avg_finish_5"].rank(method="min")
    h["team_rank"] = gr["c_best_5"].rank(method="min")
    h["grid"] = h["grid"].fillna(h["field"])
    return h


# ---------------------------------------------------------------- training
def _norm(df: pd.DataFrame, p: np.ndarray, total: float) -> np.ndarray:
    s = pd.Series(p, index=df.index)
    return (s / s.groupby(df["race"]).transform("sum") * total).clip(upper=1).values


def _race_metrics(df: pd.DataFrame, pw: np.ndarray) -> dict:
    d = df.assign(p=pw)
    hits1 = hits3 = pods = n = 0
    for _, g in d.groupby("race"):
        if g["win"].sum() != 1:
            continue
        top = g.nlargest(3, "p")
        hits1 += int(top.iloc[0]["win"] == 1)
        hits3 += int(top["win"].sum() == 1)
        pods += int(top["podium"].sum())
        n += 1
    return {"races": n, "favourite_won": hits1 / n, "winner_in_top3": hits3 / n, "podium_overlap": pods / (3 * n)}


def train() -> dict:
    h = build_features(dataset_history())
    h = h[(h["season"] >= FIRST_SEASON) & h["pos"].notna()]
    tr, te = h[h["season"] < TEST_FROM], h[h["season"] >= TEST_FROM]
    candidates = {
        "Logistic Regression": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5)),
        "Random Forest": lambda: RandomForestClassifier(n_estimators=400, min_samples_leaf=8, class_weight="balanced_subsample",
                                                        random_state=RS, n_jobs=-1),
        "Gradient Boosting": lambda: GradientBoostingClassifier(n_estimators=250, max_depth=3, learning_rate=0.05, random_state=RS),
    }
    report, artifacts = {"train_seasons": f"{FIRST_SEASON}–{TEST_FROM - 1}", "test_seasons": f"{TEST_FROM}–2024",
                         "train_rows": int(len(tr)), "test_rows": int(len(te)), "variants": {}}, {}
    for variant, feats in [("pre", PRE), ("grid", GRID)]:
        rows = []
        best = None
        for name, make in candidates.items():
            m = make().fit(tr[feats], tr["win"])
            pw = _norm(te, m.predict_proba(te[feats])[:, 1], 1.0)
            met = _race_metrics(te, pw)
            met["log_loss"] = float(log_loss(te["win"], np.clip(pw, 1e-6, 1 - 1e-6)))
            rows.append({"model": name, **met})
            if best is None or met["log_loss"] < best[1]:
                best = (name, met["log_loss"])
        name = best[0]
        win_m = candidates[name]().fit(h[feats], h["win"])       # refit on all seasons for live use
        pod_m = candidates[name]().fit(h[feats], h["podium"])
        imp = None
        if hasattr(win_m, "feature_importances_"):
            imp = sorted(({"feature": FEATURE_LABELS[f], "value": float(v)} for f, v in zip(feats, win_m.feature_importances_)),
                         key=lambda x: -x["value"])[:6]
        report["variants"][variant] = {"chosen": name, "comparison": rows, "importance": imp,
                                       "test": next(r for r in rows if r["model"] == name)}
        artifacts[variant] = {"win": win_m, "podium": pod_m, "features": feats}
        if variant == "pre":  # held-out copy (trained before TEST_FROM only) for an honest offline back-test
            artifacts["pre_holdout"] = {"win": candidates[name]().fit(tr[feats], tr["win"]),
                                        "podium": candidates[name]().fit(tr[feats], tr["podium"]), "features": feats}
    return {"artifacts": artifacts, "report": clean(report)}


# ---------------------------------------------------------------- live prediction
_cache: dict = {}
_lock = threading.Lock()


def _score(feat: pd.DataFrame, art: dict) -> pd.DataFrame:
    X = feat[art["features"]]
    out = feat.copy()
    out["p_win"] = _norm(out, art["win"].predict_proba(X)[:, 1], 1.0)
    out["p_podium"] = _norm(out, art["podium"].predict_proba(X)[:, 1], 3.0)
    return out.sort_values("p_win", ascending=False)


def _rows(df: pd.DataFrame, n: int = 10) -> list[dict]:
    return [{"driver_ref": r.driver, "name": r.driver_name, "code": r.code, "team": r.team_name, "team_ref": r.team,
             "p_win": float(r.p_win), "p_podium": float(r.p_podium),
             "form": {"avg_finish_5": float(r.d_avg_finish_5), "podiums_10": float(r.d_podium_rate_10),
                      "circuit_avg": float(r.d_circ_avg), "circuit_wins": int(r.d_circ_wins)},
             "grid": None if pd.isna(getattr(r, "qual", np.nan)) else int(r.qual),
             "actual": None if pd.isna(r.pos) else int(r.pos)} for r in df.head(n).itertuples()]


def predict_next(model: dict, race: dict) -> dict:
    """Predict the given upcoming race (a schedule entry from live.schedule())."""
    quali = live.qualifying(race["season"], race["round"]) or []
    key = (race["season"], race["round"], len(quali))  # re-predict once qualifying results appear
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < 900:
            return hit[1]
    season, rnd = race["season"], race["round"]
    hist_live, seasons = live_history(season)
    base = dataset_history()
    hist = pd.concat([base, hist_live], ignore_index=True) if len(hist_live) else base
    hist = hist[~((hist["season"] == season) & (hist["round"] == rnd))]  # the race we predict is never history

    # entrants: the line-up of the most recent race this season (falls back to last season)
    done = hist_live[hist_live["season"] == season] if len(hist_live) else hist_live
    if not len(done):
        done = hist[hist["season"] == hist["season"].max()]
    last = done[done["date"] == done["date"].max()]
    entrants = last[["driver", "driver_name", "code", "team", "team_name"]].drop_duplicates("driver")

    qpos = {q["driver"]: q["pos"] for q in quali}
    if quali:  # qualifying is the real line-up: add anyone missing (a substitute driver) by their quali team
        known = set(entrants["driver"])
        extra = [q for q in quali if q["driver"] not in known]
        if extra:
            names = hist.drop_duplicates("driver", keep="last").set_index("driver")
            entrants = pd.concat([entrants, pd.DataFrame([{
                "driver": q["driver"], "driver_name": names["driver_name"].get(q["driver"], q["driver"]),
                "code": names["code"].get(q["driver"]), "team": q["team"],
                "team_name": entrants.set_index("team")["team_name"].get(q["team"], q["team"])} for q in extra])])
        entrants = entrants[entrants["driver"].isin(qpos)]

    pending = entrants.assign(date=pd.to_datetime(race["date"]), season=season, round=rnd, circuit=race["circuit_ref"],
                              grid=entrants["driver"].map(qpos), pos=np.nan, dnf=np.nan)
    feat = build_features(pd.concat([hist, pending], ignore_index=True))
    feat = feat[(feat["season"] == season) & (feat["round"] == rnd)].copy()
    feat["qual"] = feat["driver"].map(qpos)
    variant = "grid" if quali else "pre"
    scored = _score(feat, model["artifacts"][variant])
    rep = model["report"]["variants"][variant]
    out = clean({
        "available": True, "mode": "live", "variant": variant,
        "race": {"season": season, "round": rnd, "name": race["race_name"], "circuit": race["circuit_name"],
                 "country": race["country"], "start": race["start"]},
        "uses_qualifying": bool(quali), "predictions": _rows(scored, 10),
        "model": {"name": rep["chosen"], "trained_on": model["report"]["train_seasons"] + " (refit on 2000–2024)",
                  "backtest": rep["test"], "backtest_seasons": model["report"]["test_seasons"]},
        "data_through": f"{int(hist['season'].max())} R{int(hist[hist['season'] == hist['season'].max()]['round'].max())}",
        "live_seasons": seasons, "generated_at": datetime.now(timezone.utc).isoformat(),
    })
    with _lock:
        _cache[key] = (time.time(), out)
    return out


def backtest_last(model: dict) -> dict:
    """Offline fallback: how the model would have called the last race in the dataset."""
    h = dataset_history()
    last_season = int(h["season"].max())
    last_round = int(h[h["season"] == last_season]["round"].max())
    feat = build_features(h)
    feat = feat[(feat["season"] == last_season) & (feat["round"] == last_round)].copy()
    variant = "pre"
    scored = _score(feat, model["artifacts"]["pre_holdout"])
    d = get_data()
    race = d.races[(d.races["year"] == last_season) & (d.races["round"] == last_round)].iloc[0]
    winner = feat.loc[feat["pos"] == 1, "driver_name"]
    rep = model["report"]["variants"][variant]
    return clean({
        "available": True, "mode": "backtest", "variant": variant,
        "race": {"season": last_season, "round": last_round, "name": race["race_name"], "circuit": race["circuit_name"],
                 "country": race["country"], "start": race["date"].strftime("%Y-%m-%d")},
        "uses_qualifying": False, "predictions": _rows(scored, 10),
        "actual_winner": winner.iloc[0] if len(winner) else None,
        "model": {"name": rep["chosen"], "trained_on": model["report"]["train_seasons"] + " only (this race was unseen)",
                  "backtest": rep["test"], "backtest_seasons": model["report"]["test_seasons"]},
    })
