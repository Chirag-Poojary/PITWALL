"""Machine-learning models ported from the project notebooks.

1. Points-finish classifier  (f1_naive_bayes_classification.ipynb)  Gaussian NB + Random Forest
2. Race-winner classifier    (f1_classification_project.ipynb)       Decision Tree / NB / Random Forest
3. Fastest-lap speed model   (f1_regression_project.ipynb)           Linear / Ridge / RF / Gradient Boosting
4. Driver-season clustering  (clustering.ipynb)                      K-Means (computed on demand)

Models 1-3 are trained once in a background thread when the server starts and
cached to disk (backend/models_cache.joblib) so later starts are instant.
"""
from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import mutual_info_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, f1_score,
                             mean_absolute_error, mean_squared_error, precision_recall_fscore_support,
                             r2_score, roc_auc_score, roc_curve, silhouette_score)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score, train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, PowerTransformer, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .data import clean, get_data

RS = 42
CACHE = Path(__file__).resolve().parent.parent / "models_cache.joblib"
CACHE_VERSION = 3

STATE: dict = {"status": "idle", "error": None, "started": None, "finished": None, "models": {}}
_lock = threading.Lock()


# =====================================================================
# 1. Points-finish classifier (Naive Bayes notebook)
# =====================================================================
POINTS_FEATURES = ["grid", "constructor_form", "driver_form", "round", "season", "alt", "lat", "lng"]


def _points_frame() -> pd.DataFrame:
    df = get_data().f1.copy()
    df = df[df["season"] >= 2004].copy()
    df["grid"] = df["grid"].replace(0, np.nan)
    df = df.dropna(subset=["grid"])
    df["points_finish"] = (df["positionOrder"] <= 10).astype(int)
    df = df.sort_values("date").reset_index(drop=True)
    df["constructor_form"] = df.groupby("constructorId")["points_finish"].transform(
        lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    df["driver_form"] = df.groupby("driverId")["points_finish"].transform(
        lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    base = df["points_finish"].mean()
    df["constructor_form"] = df["constructor_form"].fillna(base)
    df["driver_form"] = df["driver_form"].fillna(base)
    return df


def train_points() -> dict:
    df = _points_frame()
    X, y = df[POINTS_FEATURES], df["points_finish"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RS, stratify=y)
    majority = float(max(y_test.mean(), 1 - y_test.mean()))

    nb = GaussianNB().fit(X_train, y_train)
    p_nb = nb.predict(X_test)

    grid = GridSearchCV(Pipeline([("power", PowerTransformer()), ("nb", GaussianNB())]),
                        {"nb__var_smoothing": np.logspace(-12, 0, 13)},
                        cv=StratifiedKFold(5, shuffle=True, random_state=RS), scoring="accuracy", n_jobs=-1)
    grid.fit(X_train, y_train)
    tuned = grid.best_estimator_
    rf = RandomForestClassifier(n_estimators=300, random_state=RS, n_jobs=-1, min_samples_leaf=3).fit(X_train, y_train)

    models = {"Naive Bayes": nb, "Naive Bayes (tuned)": tuned, "Random Forest": rf}
    comparison, roc, cms = [], {}, {}
    for name, m in models.items():
        pred = m.predict(X_test)
        proba = m.predict_proba(X_test)[:, 1]
        p, r, f, _ = precision_recall_fscore_support(y_test, pred, average="binary")
        comparison.append({"model": name, "accuracy": accuracy_score(y_test, pred), "precision": p, "recall": r,
                           "f1": f, "auc": roc_auc_score(y_test, proba)})
        fpr, tpr, _ = roc_curve(y_test, proba)
        idx = np.linspace(0, len(fpr) - 1, min(len(fpr), 120)).astype(int)
        roc[name] = {"fpr": fpr[idx].round(4).tolist(), "tpr": tpr[idx].round(4).tolist()}
        cms[name] = confusion_matrix(y_test, pred).tolist()

    single = []
    for f in POINTS_FEATURES:
        m = GaussianNB().fit(X_train[[f]], y_train)
        single.append({"feature": f, "accuracy": accuracy_score(y_test, m.predict(X_test[[f]]))})
    mi = mutual_info_classif(X, y, random_state=RS)
    cv = cross_val_score(tuned, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=RS), scoring="accuracy")
    corr = X.corr().round(3)
    grid_curve = (df.groupby(df["grid"].clip(upper=24))["points_finish"].mean().reset_index()
                  .rename(columns={"points_finish": "rate"}))
    rep = classification_report(y_test, p_nb, target_names=["Outside points", "Points finish"], output_dict=True)

    return {
        "artifacts": {"nb": nb, "tuned": tuned, "rf": rf},
        "report": clean({
            "rows": len(df), "train_rows": len(X_train), "test_rows": len(X_test),
            "positive_rate": float(y.mean()), "majority_baseline": majority,
            "features": POINTS_FEATURES, "comparison": comparison, "roc": roc, "confusion": cms,
            "classification_report": rep,
            "single_feature": sorted(single, key=lambda x: -x["accuracy"]),
            "mutual_info": sorted([{"feature": f, "value": float(v)} for f, v in zip(POINTS_FEATURES, mi)],
                                  key=lambda x: -x["value"]),
            "rf_importance": sorted([{"feature": f, "value": float(v)} for f, v in zip(POINTS_FEATURES, rf.feature_importances_)],
                                    key=lambda x: -x["value"]),
            "best_var_smoothing": float(grid.best_params_["nb__var_smoothing"]), "best_cv": float(grid.best_score_),
            "cv_scores": cv.tolist(), "cv_mean": float(cv.mean()), "cv_std": float(cv.std()),
            "correlation": {"labels": list(corr.columns), "z": corr.values.tolist()},
            "grid_curve": grid_curve.to_dict("records"),
        }),
        "forms": {
            "driver": df.groupby("driverId")["points_finish"].apply(lambda s: s.tail(10).mean()).to_dict(),
            "constructor": df.groupby("constructorId")["points_finish"].apply(lambda s: s.tail(10).mean()).to_dict(),
            "base": float(df["points_finish"].mean()),
        },
    }


def predict_points(driver_id: int | None, constructor_id: int | None, grid: int, circuit_id: int,
                   season: int, rnd: int, driver_form: float | None = None, constructor_form: float | None = None) -> dict:
    m = model("points")
    forms = m["forms"]
    d = get_data()
    c = d.circuits[d.circuits["circuitId"] == circuit_id]
    if c.empty:
        raise ValueError("Unknown circuit")
    c = c.iloc[0]
    df_ = driver_form if driver_form is not None else forms["driver"].get(driver_id, forms["base"])
    cf_ = constructor_form if constructor_form is not None else forms["constructor"].get(constructor_id, forms["base"])
    row = pd.DataFrame([{"grid": grid, "constructor_form": cf_, "driver_form": df_, "round": rnd, "season": season,
                         "alt": c["alt"], "lat": c["lat"], "lng": c["lng"]}])[POINTS_FEATURES]
    a = m["artifacts"]
    return clean({
        "inputs": row.iloc[0].to_dict(),
        "probabilities": {"Naive Bayes": float(a["nb"].predict_proba(row)[0, 1]),
                          "Naive Bayes (tuned)": float(a["tuned"].predict_proba(row)[0, 1]),
                          "Random Forest": float(a["rf"].predict_proba(row)[0, 1])},
    })


# =====================================================================
# 2. Race-winner (constructor) classifier
# =====================================================================
WIN_FEATURES = ["best_grid", "prev_wins_10", "prev_podiums_10", "career_wins", "circuit_prev_wins", "avg_grid_5"]
MIN_SEASON, TEST_FROM = 2000, 2018


def train_winner() -> dict:
    df = get_data().f1
    winners_all = df[df["positionOrder"] == 1][["raceId", "constructor_name"]]
    top10 = (winners_all.merge(df[["raceId", "season"]].drop_duplicates(), on="raceId")
             .query("season >= @MIN_SEASON")["constructor_name"].value_counts().head(10).index.tolist())
    rc = (df[df["season"] >= MIN_SEASON]
          .groupby(["raceId", "season", "round", "date", "circuitId", "constructor_name"], as_index=False)
          .agg(best_grid=("grid", lambda s: s.replace(0, np.nan).min()), n_cars=("grid", "size")))
    rw = df[df["positionOrder"] == 1][["raceId", "constructor_name"]].rename(columns={"constructor_name": "winner"})
    rc = rc.merge(rw, on="raceId")
    rc = rc[rc["winner"].isin(top10)].copy()
    rc = rc.sort_values(["constructor_name", "date"]).reset_index(drop=True)
    rc["won"] = (rc["constructor_name"] == rc["winner"]).astype(int)

    def roll_sum(col, w):
        return rc.groupby("constructor_name")[col].transform(lambda s: s.shift(1).rolling(w, min_periods=1).sum())

    rc["prev_wins_10"] = roll_sum("won", 10)
    rc["career_wins"] = rc.groupby("constructor_name")["won"].transform(lambda s: s.shift(1).expanding().sum())
    rc["circuit_prev_wins"] = rc.groupby(["constructor_name", "circuitId"])["won"].transform(lambda s: s.shift(1).expanding().sum())
    rc["avg_grid_5"] = rc.groupby("constructor_name")["best_grid"].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    pod = (df[df["positionOrder"].isin([1, 2, 3])].groupby(["raceId", "constructor_name"]).size().clip(upper=1)
           .rename("podium_flag").reset_index())
    rc = rc.merge(pod, on=["raceId", "constructor_name"], how="left")
    rc["podium_flag"] = rc["podium_flag"].fillna(0)
    rc = rc.sort_values(["constructor_name", "date"]).reset_index(drop=True)
    rc["prev_podiums_10"] = roll_sum("podium_flag", 10)

    top = rc[rc["constructor_name"].isin(top10)]
    wide = top.pivot_table(index=["raceId", "season", "round", "date", "circuitId", "winner"],
                           columns="constructor_name", values=WIN_FEATURES, aggfunc="first")
    wide.columns = [f"{c}__{f}" for f, c in wide.columns]
    wide = wide.reset_index().sort_values("date").reset_index(drop=True)
    wide["month"] = pd.to_datetime(wide["date"]).dt.month
    wide["era"] = pd.cut(wide["season"], bins=[1999, 2005, 2013, 2021, 2030],
                         labels=["V10", "V8", "V6_hybrid", "ground_effect"]).astype(str)
    grid_cols = [c for c in wide.columns if "best_grid" in c or "avg_grid_5" in c]
    form_cols = [c for c in wide.columns if any(k in c for k in ["prev_wins", "prev_podiums", "career_wins", "circuit_prev_wins"])]
    wide[grid_cols] = SimpleImputer(strategy="constant", fill_value=21).fit_transform(wide[grid_cols])
    wide[form_cols] = SimpleImputer(strategy="constant", fill_value=0).fit_transform(wide[form_cols])

    enc = LabelEncoder()
    y = enc.fit_transform(wide["winner"])
    classes = list(enc.classes_)
    X = wide[grid_cols + form_cols + ["month"]].copy()
    X = pd.concat([X, pd.get_dummies(wide["era"], prefix="era").astype(int)], axis=1)
    for e in ["era_V10", "era_V8", "era_V6_hybrid", "era_ground_effect"]:
        if e not in X.columns:
            X[e] = 0
    tr, te = wide["season"] < TEST_FROM, wide["season"] >= TEST_FROM
    X_train, X_test, y_train, y_test = X[tr], X[te], y[tr], y[te]

    models = {
        "Decision Tree": DecisionTreeClassifier(criterion="entropy", max_depth=6, min_samples_leaf=3, random_state=RS),
        "Naive Bayes": GaussianNB(),
        "Random Forest": RandomForestClassifier(n_estimators=300, max_depth=10, min_samples_leaf=2, random_state=RS, n_jobs=-1),
    }
    comparison, cms, preds = [], {}, {}
    labels_present = None
    for name, m in models.items():
        m.fit(X_train, y_train)
        p = m.predict(X_test)
        preds[name] = p
        pr, rcl, f, _ = precision_recall_fscore_support(y_test, p, average="macro", zero_division=0)
        comparison.append({"model": name, "accuracy": accuracy_score(y_test, p), "precision": pr, "recall": rcl, "f1": f})
        labels_present = np.unique(np.concatenate([y_test, p]))
        cms[name] = {"labels": [classes[i] for i in np.unique(np.concatenate([y_test, p]))],
                     "z": confusion_matrix(y_test, p, labels=np.unique(np.concatenate([y_test, p]))).tolist()}
    rf = models["Random Forest"]
    imp = sorted(zip(X.columns, rf.feature_importances_), key=lambda t: -t[1])[:15]
    mi = mutual_info_classif(X, y, random_state=RS)
    mi_top = sorted(zip(X.columns, mi), key=lambda t: -t[1])[:15]

    # per-season test accuracy for RF
    te_df = wide[te][["season"]].copy()
    te_df["ok"] = preds["Random Forest"] == y_test
    by_season = te_df.groupby("season")["ok"].mean().reset_index()

    # template row for scenarios: most recent race
    template = X.iloc[[-1]].copy()
    last_meta = wide.iloc[-1]
    template_info = {c: {"best_grid": float(template[f"{c}__best_grid"].iloc[0]) if f"{c}__best_grid" in template else 21.0,
                         "prev_wins_10": float(template.get(f"{c}__prev_wins_10", pd.Series([0])).iloc[0]),
                         "prev_podiums_10": float(template.get(f"{c}__prev_podiums_10", pd.Series([0])).iloc[0])}
                     for c in top10}
    return {
        "artifacts": {"models": models, "columns": list(X.columns), "classes": classes, "template": template},
        "report": clean({
            "top10": top10, "classes": classes, "train_races": int(tr.sum()), "test_races": int(te.sum()),
            "test_from": TEST_FROM, "n_features": X.shape[1], "comparison": comparison, "confusion": cms,
            "class_distribution": pd.Series(wide["winner"]).value_counts().to_dict(),
            "rf_importance": [{"feature": f, "value": float(v)} for f, v in imp],
            "mutual_info": [{"feature": f, "value": float(v)} for f, v in mi_top],
            "rf_by_season": by_season.to_dict("records"),
            "template_race": {"season": int(last_meta["season"]), "round": int(last_meta["round"]),
                              "teams": template_info},
        }),
    }


def predict_winner(grids: dict, form: dict | None = None) -> dict:
    m = model("winner")
    a = m["artifacts"]
    row = a["template"].copy()
    for team, g in grids.items():
        col = f"{team}__best_grid"
        if col in row.columns and g is not None:
            row[col] = float(g)
    for team, vals in (form or {}).items():
        for k, v in vals.items():
            col = f"{team}__{k}"
            if col in row.columns and v is not None:
                row[col] = float(v)
    out = {}
    for name, mdl in a["models"].items():
        proba = mdl.predict_proba(row[a["columns"]])[0]
        out[name] = sorted([{"team": a["classes"][i], "p": float(p)} for i, p in enumerate(proba)], key=lambda x: -x["p"])
    return clean(out)


# =====================================================================
# 3. Fastest-lap speed regression
# =====================================================================
REG_NUM = ["grid", "season", "round", "driver_age", "driver_experience", "driver_form", "constructor_form",
           "circuit_avg_speed", "lat", "lng", "alt"]
REG_CAT = ["circuit_country"]


def train_regression() -> dict:
    df = get_data().f1.copy()
    df = df.sort_values(["date", "driverId"]).reset_index(drop=True)
    df = df[(df["laps"] >= 5) & (df["season"] >= 2004)].reset_index(drop=True)
    missing_before = int(df["fastestLapSpeed"].isna().sum())
    df["driver_age"] = (df["date"] - df["dob"]).dt.days / 365.25
    df["driver_experience"] = df.groupby("driverId").cumcount()
    df["driver_form"] = df.groupby("driverId")["fastestLapSpeed"].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    df["constructor_form"] = df.groupby("constructorId")["fastestLapSpeed"].transform(lambda x: x.shift(1).rolling(10, min_periods=1).mean())
    df["circuit_avg_speed"] = df.groupby("circuitId")["fastestLapSpeed"].transform(lambda x: x.shift(1).expanding().mean())
    mean_speed = df["fastestLapSpeed"].mean()
    for col in ["driver_form", "constructor_form", "circuit_avg_speed"]:
        df[col] = df[col].fillna(mean_speed)
    mdf = df.dropna(subset=REG_NUM + REG_CAT + ["fastestLapSpeed"])
    train, test = mdf[mdf["date"].dt.year <= 2020], mdf[mdf["date"].dt.year >= 2021]
    Xtr, ytr = train[REG_NUM + REG_CAT], train["fastestLapSpeed"]
    Xte, yte = test[REG_NUM + REG_CAT], test["fastestLapSpeed"]

    def pre():
        return ColumnTransformer([("num", StandardScaler(), REG_NUM),
                                  ("cat", OneHotEncoder(handle_unknown="ignore"), REG_CAT)])

    models = {
        "Linear Regression": LinearRegression(),
        "Ridge Regression": Ridge(alpha=1.0, random_state=RS),
        "Random Forest": RandomForestRegressor(n_estimators=300, max_depth=12, random_state=RS, n_jobs=-1),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.1, random_state=RS),
    }
    fitted, comp, preds = {}, [], {}
    for name, mdl in models.items():
        pipe = Pipeline([("preprocess", pre()), ("model", mdl)]).fit(Xtr, ytr)
        p = pipe.predict(Xte)
        fitted[name], preds[name] = pipe, p
        comp.append({"model": name, "mae": mean_absolute_error(yte, p), "rmse": float(np.sqrt(mean_squared_error(yte, p))),
                     "r2": r2_score(yte, p)})
    comp.sort(key=lambda x: x["rmse"])
    best = comp[0]["model"]
    rfp = fitted["Random Forest"]
    names = REG_NUM + list(rfp.named_steps["preprocess"].named_transformers_["cat"].get_feature_names_out(REG_CAT))
    imp = sorted(zip(names, rfp.named_steps["model"].feature_importances_), key=lambda t: -t[1])[:15]
    rng = np.random.default_rng(RS)
    idx = rng.choice(len(yte), size=min(1200, len(yte)), replace=False)
    t2 = test.assign(pred=preds[best], err=lambda x: x["pred"] - x["fastestLapSpeed"])
    by_circuit = (t2.groupby("circuit_name").agg(mae=("err", lambda e: float(np.abs(e).mean())), n=("err", "size"),
                                                 actual=("fastestLapSpeed", "mean"), predicted=("pred", "mean"))
                  .reset_index().sort_values("mae", ascending=False))
    corr = df[REG_NUM + ["fastestLapSpeed"]].corr().round(3)
    return {
        "artifacts": {"best": fitted[best]},
        "report": clean({
            "rows": len(mdf), "train_rows": len(train), "test_rows": len(test), "missing_target_rows": missing_before,
            "features": REG_NUM + REG_CAT, "comparison": comp, "best_model": best,
            "rf_importance": [{"feature": f, "value": float(v)} for f, v in imp],
            "scatter": {"actual": yte.values[idx].round(2).tolist(), "predicted": np.round(preds[best][idx], 2).tolist(),
                        "circuit": test["circuit_name"].values[idx].tolist(), "season": test["season"].values[idx].tolist()},
            "residuals": np.round(preds[best] - yte.values, 2)[idx].tolist(),
            "by_circuit": by_circuit.round(2).to_dict("records"),
            "correlation": {"labels": list(corr.columns), "z": corr.values.tolist()},
        }),
    }


# =====================================================================
# 4. K-Means clustering (computed on demand with filters)
# =====================================================================
TIER_NAMES = {
    2: ["Front half", "Back half"],
    3: ["Front-runners", "Midfield", "Backmarkers"],
    4: ["Front-runners / Title contenders", "Upper midfield (regular points)",
        "Lower midfield (occasional points)", "Backmarkers"],
    5: ["Title contenders", "Front-runners", "Upper midfield", "Lower midfield", "Backmarkers"],
    6: ["Title contenders", "Front-runners", "Upper midfield", "Midfield", "Lower midfield", "Backmarkers"],
}


def clustering(k: int = 4, season_from: int = 2004, season_to: int = 2024, min_races: int = 5,
               features: tuple[str, ...] = ("avg_grid", "avg_finish")) -> dict:
    raw = get_data().f1
    raw = raw[(raw["season"] >= season_from) & (raw["season"] <= season_to)].copy()
    raw["grid"] = raw["grid"].replace(0, np.nan)
    raw["is_points"] = (raw["positionOrder"] <= 10).astype(int)
    df = (raw.groupby(["driverId", "driver_name", "season"])
          .agg(races=("resultId", "size"), avg_grid=("grid", "mean"), avg_finish=("positionOrder", "mean"),
               total_points=("points", "sum"), points_rate=("is_points", "mean"),
               team=("constructor_name", lambda s: s.mode().iloc[0]))
          .reset_index())
    df = df[df["races"] >= min_races].dropna(subset=list(features)).reset_index(drop=True)
    if len(df) < max(10, k + 1):
        raise ValueError("Not enough driver-seasons for this filter")
    X = df[list(features)]
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    elbow = []
    for kk in range(1, 11):
        km = KMeans(n_clusters=kk, random_state=RS, n_init=10).fit(Xs)
        elbow.append({"k": kk, "inertia": float(km.inertia_),
                      "silhouette": float(silhouette_score(Xs, km.labels_)) if kk > 1 else None})
    km = KMeans(n_clusters=k, random_state=RS, n_init=10).fit(Xs)
    df["cluster"] = km.labels_
    centers = scaler.inverse_transform(km.cluster_centers_)
    summary = df.groupby("cluster").agg(avg_grid=("avg_grid", "mean"), avg_finish=("avg_finish", "mean"),
                                        total_points=("total_points", "mean"), n=("driverId", "size")).reset_index()
    order = summary.sort_values("avg_finish")["cluster"].tolist()
    names = TIER_NAMES.get(k, [f"Tier {i + 1}" for i in range(k)])
    tier = {cl: names[i] if i < len(names) else f"Tier {i + 1}" for i, cl in enumerate(order)}
    rank = {cl: i for i, cl in enumerate(order)}
    df["tier"] = df["cluster"].map(tier)
    df["tier_rank"] = df["cluster"].map(rank)
    summary["tier"] = summary["cluster"].map(tier)
    summary["tier_rank"] = summary["cluster"].map(rank)
    top = (df.sort_values("total_points", ascending=False).groupby("tier_rank").head(5)
           [["tier_rank", "tier", "driver_name", "season", "team", "avg_grid", "avg_finish", "total_points"]]
           .sort_values(["tier_rank", "total_points"], ascending=[True, False]))
    return clean({
        "k": k, "features": list(features), "n": len(df),
        "silhouette": float(silhouette_score(Xs, km.labels_)), "elbow": elbow,
        "centroids": [{"cluster": int(i), "tier": tier[i], "tier_rank": rank[i],
                       **{f: float(c[j]) for j, f in enumerate(features)}} for i, c in enumerate(centers)],
        "summary": summary.round(2).sort_values("tier_rank").to_dict("records"),
        "points": df[["driverId", "driver_name", "season", "team", "races", "avg_grid", "avg_finish", "total_points",
                      "points_rate", "cluster", "tier", "tier_rank"]].round(3).to_dict("records"),
        "top_members": top.round(2).to_dict("records"),
    })


# =====================================================================
# training orchestration
# =====================================================================
TRAINERS = {"points": train_points, "winner": train_winner, "regression": train_regression}


def _train_all() -> None:
    STATE.update(status="training", error=None, started=time.time())
    try:
        if CACHE.exists():
            try:
                cached = joblib.load(CACHE)
                if cached.get("version") == CACHE_VERSION:
                    STATE["models"] = cached["models"]
                    STATE.update(status="ready", finished=time.time())
                    return
            except Exception:
                try:
                    CACHE.unlink(missing_ok=True)
                except OSError:
                    pass
        out = {}
        for name, fn in TRAINERS.items():
            STATE["current"] = name
            out[name] = fn()
            STATE["models"][name] = out[name]
        try:
            joblib.dump({"version": CACHE_VERSION, "models": out}, CACHE, compress=3)
        except OSError:
            pass  # Read-only filesystem (e.g. Vercel), models remain in memory
        STATE.update(status="ready", finished=time.time(), current=None)
    except Exception as e:  # pragma: no cover
        STATE.update(status="error", error=f"{e}\n{traceback.format_exc()}")


def start_training(force: bool = False) -> None:
    with _lock:
        if STATE["status"] == "training":
            return
        if force and CACHE.exists():
            CACHE.unlink()
            STATE["models"] = {}
        threading.Thread(target=_train_all, daemon=True).start()


def model(name: str) -> dict:
    m = STATE["models"].get(name)
    if m is None:
        raise RuntimeError("Models are still training")
    return m


def status() -> dict:
    return {"status": STATE["status"], "ready": list(STATE["models"].keys()), "current": STATE.get("current"),
            "error": STATE["error"]}
