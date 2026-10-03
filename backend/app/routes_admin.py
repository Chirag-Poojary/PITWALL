"""Analyst dashboard endpoints (admin role only)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import ml
from .auth import require_admin
from .data import clean, get_data, records

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ------------------------------------------------------------------ helpers
def _ids(s: str | None) -> list[int]:
    return [int(x) for x in s.split(",") if x.strip().isdigit()] if s else []


def _range(df: pd.DataFrame, f: int | None, t: int | None, col: str = "year") -> pd.DataFrame:
    if f:
        df = df[df[col] >= f]
    if t:
        df = df[df[col] <= t]
    return df


def _laptime(s) -> float:
    if not isinstance(s, str) or ":" not in s:
        try:
            return float(s)
        except (TypeError, ValueError):
            return np.nan
    m, sec = s.split(":", 1)
    try:
        return int(m) * 60 + float(sec)
    except ValueError:
        return np.nan


STATUS_GROUPS = [
    ("Accident / Collision", ["accident", "collision", "spun", "damage", "debris", "fatal"]),
    ("Engine / Power unit", ["engine", "power", "ers", "turbo", "overheat", "oil", "water", "fuel", "radiator", "cooling",
                             "battery", "exhaust", "supercharger", "injection", "spark", "magneto", "distributor",
                             "crankshaft", "heat shield", "fire", "ignition", "alternator"]),
    ("Gearbox / Driveline", ["gearbox", "transmission", "clutch", "driveshaft", "differential", "halfshaft",
                             "drivetrain", "axle", "cv joint"]),
    ("Hydraulics / Electrics", ["hydraulic", "electric", "electronic", "pneumatic", "throttle", "launch"]),
    ("Chassis / Brakes / Tyres", ["suspension", "brake", "wheel", "tyre", "puncture", "steering", "track rod", "wing",
                                  "undertray", "chassis", "handling", "vibration", "seat", "safety belt", "mirror"]),
    ("Disqualified", ["disqualified", "excluded", "underweight"]),
    ("Did not start / qualify", ["did not", "107%", "withdrew", "not restarted", "not classified"]),
    ("Driver (injury / illness)", ["injur", "illness", "unwell", "physical", "eye"]),
]


def status_group(s: str | None, finished: bool) -> str:
    if finished:
        return "Finished"
    sl = (s or "").lower()
    for name, keys in STATUS_GROUPS:
        if any(k in sl for k in keys):
            return name
    return "Other / Retired"


@lru_cache(maxsize=1)
def _res() -> pd.DataFrame:
    d = get_data()
    r = d.res.copy()
    r["status_group"] = [status_group(s, f) for s, f in zip(r["status"], r["finished"])]
    r["grid0"] = r["grid"].replace(0, np.nan)
    r["gained"] = r["grid0"] - r["positionOrder"]
    return r


@lru_cache(maxsize=1)
def _quali() -> pd.DataFrame:
    d = get_data()
    q = d.qualifying.copy()
    for c in ["q1", "q2", "q3"]:
        q[c + "_s"] = q[c].map(_laptime)
    q["best"] = q[["q1_s", "q2_s", "q3_s"]].min(axis=1)
    q = q.merge(d.races[["raceId", "year", "round", "race_name"]], on="raceId")
    pole = q.groupby("raceId")["best"].transform("min")
    q["gap_pct"] = (q["best"] / pole - 1) * 100
    q = q.merge(d.constructors[["constructorId", "name"]].rename(columns={"name": "constructor_name"}), on="constructorId")
    q = q.merge(d.drivers[["driverId", "name"]].rename(columns={"name": "driver_name"}), on="driverId")
    return q


@lru_cache(maxsize=1)
def _pits() -> pd.DataFrame:
    d = get_data()
    p = d.pit_stops.copy()
    p["duration_s"] = pd.to_numeric(p["milliseconds"], errors="coerce") / 1000
    p = p.merge(d.races[["raceId", "year", "round", "race_name"]], on="raceId")
    team = d.results[["raceId", "driverId", "constructorId"]]
    p = p.merge(team, on=["raceId", "driverId"], how="left")
    p = p.merge(d.constructors[["constructorId", "name"]].rename(columns={"name": "constructor_name"}), on="constructorId", how="left")
    p = p.merge(d.drivers[["driverId", "name"]].rename(columns={"name": "driver_name"}), on="driverId", how="left")
    p["valid"] = p["duration_s"].between(10, 60)  # drop red-flag / drive-through artefacts
    return p


def _top_constructors(df: pd.DataFrame, n: int, by: str = "points") -> list[str]:
    return df.groupby("constructor_name")[by].sum().sort_values(ascending=False).head(n).index.tolist()


# ------------------------------------------------------------------ filters
@router.get("/filters")
def filters():
    d = get_data()
    r = d.res
    drv = (r.groupby(["driverId", "driver_name"]).agg(first=("year", "min"), last=("year", "max"),
                                                      points=("points", "sum")).reset_index()
           .sort_values(["last", "points"], ascending=False))
    cons = (r.groupby(["constructorId", "constructor_name"]).agg(first=("year", "min"), last=("year", "max"),
                                                                 points=("points", "sum")).reset_index()
            .sort_values(["last", "points"], ascending=False))
    circ = (d.races.groupby(["circuitId", "circuit_name", "country"]).agg(races=("raceId", "size"), last=("year", "max"))
            .reset_index().sort_values(["last", "races"], ascending=False))
    return {"seasons": d.seasons, "drivers": records(drv), "constructors": records(cons), "circuits": records(circ)}


# ------------------------------------------------------------------ overview
@router.get("/overview")
def overview(season_from: int = 2010, season_to: int = 2024):
    d = get_data()
    r = _range(_res(), season_from, season_to)
    if r.empty:
        raise HTTPException(400, "No data in range")
    wins = r[r["positionOrder"] == 1]
    poles = r[r["grid"] == 1]
    pole_win = poles["positionOrder"].eq(1).mean() if len(poles) else None
    pits = _range(_pits(), season_from, season_to)
    kpis = {
        "seasons": int(r["year"].nunique()), "races": int(r["raceId"].nunique()), "drivers": int(r["driverId"].nunique()),
        "constructors": int(r["constructorId"].nunique()), "winners": int(wins["driverId"].nunique()),
        "winning_teams": int(wins["constructorId"].nunique()), "dnf_rate": float(r["dnf"].mean()),
        "pole_to_win": float(pole_win) if pole_win is not None else None,
        "median_pit": float(pits.loc[pits["valid"], "duration_s"].median()) if len(pits) else None,
        "avg_positions_gained_winner": float(wins["gained"].mean()),
    }
    top = _top_constructors(wins.assign(points=1), 8, "points")
    w = wins.assign(team=np.where(wins["constructor_name"].isin(top), wins["constructor_name"], "Other"))
    wins_tbl = w.groupby(["year", "team"]).size().unstack(fill_value=0)
    by_season = r.groupby("year").agg(dnf_rate=("dnf", "mean"), drivers=("driverId", "nunique"),
                                      races=("raceId", "nunique")).reset_index()
    by_season = by_season.merge(wins.groupby("year")["driverId"].nunique().rename("unique_winners").reset_index(), on="year")
    pw = poles.groupby("year")["positionOrder"].apply(lambda x: (x == 1).mean()).rename("pole_to_win").reset_index()
    by_season = by_season.merge(pw, on="year", how="left")
    fs = d.final_driver_st
    gap = (fs[fs["position"].isin([1, 2])].pivot_table(index="year", columns="position", values="points")
           .reset_index())
    gap["title_margin"] = gap[1] - gap[2]
    by_season = by_season.merge(gap[["year", "title_margin"]], on="year", how="left")
    champs = fs[fs["position"] == 1].merge(d.drivers[["driverId", "name"]], on="driverId")[["year", "name", "points"]]
    by_season = by_season.merge(champs.rename(columns={"name": "champion", "points": "champion_points"}), on="year", how="left")
    top_drivers = (r.groupby(["driverId", "driver_name"]).agg(
        points=("points", "sum"), wins=("positionOrder", lambda x: int((x == 1).sum())),
        podiums=("positionOrder", lambda x: int((x <= 3).sum())), poles=("grid", lambda x: int((x == 1).sum())),
        starts=("raceId", "size"), avg_finish=("positionOrder", "mean"), dnf_rate=("dnf", "mean"))
        .reset_index().sort_values("points", ascending=False).head(15))
    share = r.groupby("constructor_name")["points"].sum().sort_values(ascending=False)
    share = pd.concat([share.head(9), pd.Series({"Other": share.iloc[9:].sum()})]) if len(share) > 9 else share
    return clean({
        "kpis": kpis,
        "wins_by_constructor": {"seasons": wins_tbl.index.tolist(),
                                "series": [{"name": c, "values": wins_tbl[c].tolist()} for c in wins_tbl.columns]},
        "by_season": records(by_season.round(4)),
        "top_drivers": records(top_drivers.round(3)),
        "points_share": [{"name": k, "value": float(v)} for k, v in share.items()],
    })


# ------------------------------------------------------------------ drivers
def _teammate_h2h(r: pd.DataFrame, driver_id: int) -> dict:
    mine = r[r["driverId"] == driver_id][["raceId", "constructorId", "positionOrder", "dnf", "year"]]
    mates = r[["raceId", "constructorId", "driverId", "positionOrder", "dnf", "driver_name"]]
    m = mine.merge(mates, on=["raceId", "constructorId"], suffixes=("", "_tm"))
    m = m[m["driverId"] != driver_id]
    both_fin = m[~m["dnf"] & ~m["dnf_tm"]]
    race = {"ahead": int((both_fin["positionOrder"] < both_fin["positionOrder_tm"]).sum()),
            "behind": int((both_fin["positionOrder"] > both_fin["positionOrder_tm"]).sum())}
    q = _quali()
    qm = q[q["driverId"] == driver_id][["raceId", "constructorId", "position"]]
    qq = qm.merge(q[["raceId", "constructorId", "driverId", "position"]], on=["raceId", "constructorId"], suffixes=("", "_tm"))
    qq = qq[qq["driverId"] != driver_id]
    quali = {"ahead": int((qq["position"] < qq["position_tm"]).sum()), "behind": int((qq["position"] > qq["position_tm"]).sum())}
    by_mate = (both_fin.assign(ahead=both_fin["positionOrder"] < both_fin["positionOrder_tm"])
               .groupby("driver_name").agg(races=("ahead", "size"), ahead=("ahead", "sum")).reset_index()
               .sort_values("races", ascending=False).head(8))
    return {"race": race, "quali": quali, "by_teammate": records(by_mate)}


@router.get("/drivers/compare")
def driver_compare(ids: str, season_from: int | None = None, season_to: int | None = None):
    id_list = _ids(ids)[:6]
    if not id_list:
        raise HTTPException(400, "Pick at least one driver")
    r = _range(_res(), season_from, season_to)
    out = []
    for i in id_list:
        x = r[r["driverId"] == i]
        if x.empty:
            continue
        season = x.groupby("year").agg(points=("points", "sum"), wins=("positionOrder", lambda s: int((s == 1).sum())),
                                       podiums=("positionOrder", lambda s: int((s <= 3).sum())),
                                       avg_grid=("grid0", "mean"), avg_finish=("positionOrder", "mean"),
                                       dnf_rate=("dnf", "mean"), races=("raceId", "size")).reset_index()
        fs = get_data().final_driver_st
        season = season.merge(fs[fs["driverId"] == i][["year", "position"]].rename(columns={"position": "champ_pos"}),
                               on="year", how="left")
        fin = x[x["finished"]]["positionOrder"].clip(upper=20).value_counts().sort_index()
        q = _quali()
        qx = _range(q[q["driverId"] == i], season_from, season_to)
        out.append({
            "driverId": i, "name": x["driver_name"].iloc[0], "code": x["code"].iloc[0],
            "summary": {"starts": len(x), "points": float(x["points"].sum()), "wins": int((x["positionOrder"] == 1).sum()),
                        "podiums": int((x["positionOrder"] <= 3).sum()), "poles": int((x["grid"] == 1).sum()),
                        "avg_grid": float(x["grid0"].mean()), "avg_finish": float(x["positionOrder"].mean()),
                        "avg_gained": float(x["gained"].mean()), "dnf_rate": float(x["dnf"].mean()),
                        "points_per_race": float(x["points"].mean()),
                        "avg_quali_gap_pct": float(qx["gap_pct"].median()) if len(qx) else None},
            "seasons": records(season.round(3)),
            "finish_distribution": [{"position": int(k), "count": int(v)} for k, v in fin.items()],
            "grid_vs_finish": records(x[x["finished"]][["grid0", "positionOrder", "year", "race_name"]].dropna().tail(400)),
            "status_groups": x["status_group"].value_counts().to_dict(),
            "teammate": _teammate_h2h(r, i),
        })
    return clean({"drivers": out})


# ------------------------------------------------------------------ constructors
@router.get("/constructors/compare")
def constructor_compare(ids: str, season_from: int | None = None, season_to: int | None = None):
    id_list = _ids(ids)[:6]
    if not id_list:
        raise HTTPException(400, "Pick at least one constructor")
    r = _range(_res(), season_from, season_to)
    q = _range(_quali(), season_from, season_to)
    p = _range(_pits(), season_from, season_to)
    out = []
    for i in id_list:
        x = r[r["constructorId"] == i]
        if x.empty:
            continue
        season = x.groupby("year").agg(points=("points", "sum"), wins=("positionOrder", lambda s: int((s == 1).sum())),
                                       podiums=("positionOrder", lambda s: int((s <= 3).sum())),
                                       dnf_rate=("dnf", "mean"), avg_finish=("positionOrder", "mean"),
                                       races=("raceId", "nunique")).reset_index()
        season["points_per_race"] = season["points"] / season["races"]
        qg = (q[q["constructorId"] == i].groupby(["year", "raceId"])["gap_pct"].min().groupby("year").median()
              .rename("quali_gap_pct").reset_index())
        pg = (p[(p["constructorId"] == i) & p["valid"]].groupby("year")["duration_s"].median()
              .rename("median_pit_s").reset_index())
        season = season.merge(qg, on="year", how="left").merge(pg, on="year", how="left")
        fs = get_data().final_cons_st
        season = season.merge(fs[fs["constructorId"] == i][["year", "position"]].rename(columns={"position": "champ_pos"}),
                               on="year", how="left")
        out.append({
            "constructorId": i, "name": x["constructor_name"].iloc[0],
            "summary": {"races": int(x["raceId"].nunique()), "points": float(x["points"].sum()),
                        "wins": int((x["positionOrder"] == 1).sum()), "podiums": int((x["positionOrder"] <= 3).sum()),
                        "poles": int((x["grid"] == 1).sum()), "dnf_rate": float(x["dnf"].mean()),
                        "one_twos": int(x[x["positionOrder"] <= 2].groupby("raceId").size().eq(2).sum())},
            "seasons": records(season.round(3)),
            "status_groups": x[x["dnf"]]["status_group"].value_counts().to_dict(),
            "drivers": records(x.groupby("driver_name").agg(races=("raceId", "size"), points=("points", "sum"))
                               .reset_index().sort_values("points", ascending=False).head(10)),
        })
    return clean({"constructors": out})


# ------------------------------------------------------------------ race analysis
@router.get("/races")
def races(season: int):
    d = get_data()
    r = d.races[d.races["year"] == season].sort_values("round")
    have_laps = d.race_ids_with_laps()
    r = r.assign(has_laps=r["raceId"].isin(have_laps), date=r["date"].dt.strftime("%Y-%m-%d"))
    return records(r[["raceId", "round", "race_name", "date", "circuit_name", "country", "has_laps"]])


@router.get("/race/{race_id}")
def race(race_id: int):
    d = get_data()
    info = d.races[d.races["raceId"] == race_id]
    if info.empty:
        raise HTTPException(404, "Race not found")
    info = info.iloc[0]
    res = _res()
    rr = res[res["raceId"] == race_id].sort_values("positionOrder")
    table = rr[["positionOrder", "positionText", "driverId", "driver_name", "code", "constructor_name", "grid", "laps",
                "time", "status", "points", "fastestLapTime", "rank", "gained"]]
    lt = d.lap_times_for_race(race_id)
    codes = rr.set_index("driverId")["code"].fillna(rr.set_index("driverId")["driver_name"]).to_dict()
    names = rr.set_index("driverId")["driver_name"].to_dict()
    teams = rr.set_index("driverId")["constructor_name"].to_dict()
    laps = []
    if not lt.empty:
        lt["t"] = lt["milliseconds"] / 1000
        lt = lt.sort_values(["driverId", "lap"])
        lt["cum"] = lt.groupby("driverId")["t"].cumsum()
        leader = lt.groupby("lap")["cum"].min()
        lt["gap"] = lt["cum"] - lt["lap"].map(leader)
        for did, g in lt.groupby("driverId"):
            laps.append({"driverId": int(did), "code": codes.get(did) or str(did), "name": names.get(did),
                         "team": teams.get(did), "lap": g["lap"].tolist(), "position": g["position"].tolist(),
                         "time": g["t"].round(3).tolist(), "gap": g["gap"].round(3).tolist()})
        order = {did: i for i, did in enumerate(rr["driverId"])}
        laps.sort(key=lambda x: order.get(x["driverId"], 99))
    pits = _pits()
    ps = pits[pits["raceId"] == race_id][["driverId", "driver_name", "constructor_name", "stop", "lap", "duration_s"]]
    ps = ps.assign(code=ps["driverId"].map(codes))
    q = _quali()
    qq = q[q["raceId"] == race_id].sort_values("position")[["position", "driver_name", "constructor_name", "q1", "q2", "q3", "gap_pct"]]
    return clean({
        "race": {"raceId": race_id, "name": info["race_name"], "season": int(info["year"]), "round": int(info["round"]),
                 "date": info["date"].strftime("%Y-%m-%d"), "circuit": info["circuit_name"], "country": info["country"]},
        "results": records(table), "laps": laps, "pit_stops": records(ps), "qualifying": records(qq),
    })


# ------------------------------------------------------------------ qualifying
@router.get("/qualifying")
def qualifying(season_from: int = 2014, season_to: int = 2024, constructors: str | None = None):
    q = _range(_quali(), season_from, season_to).dropna(subset=["gap_pct"])
    q = q[q["gap_pct"] < 10]  # strip wet / failed laps outliers
    ids = _ids(constructors)
    best = q.groupby(["year", "raceId", "constructorId", "constructor_name"])["gap_pct"].min().reset_index()
    if ids:
        best = best[best["constructorId"].isin(ids)]
    else:
        keep = best.groupby("constructor_name")["gap_pct"].median().nsmallest(8).index
        best = best[best["constructor_name"].isin(keep)]
    trend = best.groupby(["year", "constructor_name"])["gap_pct"].median().reset_index()
    r = _range(_res(), season_from, season_to)
    fin = r[r["finished"] & r["grid0"].notna()]
    mat = pd.crosstab(fin["grid0"].clip(upper=20).astype(int), fin["positionOrder"].clip(upper=20).astype(int))
    by_grid = (r[r["grid0"].notna()].assign(g=lambda x: x["grid0"].clip(upper=20).astype(int))
               .groupby("g").agg(win_rate=("positionOrder", lambda s: (s == 1).mean()),
                                 podium_rate=("positionOrder", lambda s: (s <= 3).mean()),
                                 points_rate=("positionOrder", lambda s: (s <= 10).mean()),
                                 avg_finish=("positionOrder", "mean"), n=("raceId", "size")).reset_index())
    corr = float(fin[["grid0", "positionOrder"]].corr(method="spearman").iloc[0, 1]) if len(fin) > 3 else None
    return clean({
        "gap_trend": records(trend.round(3)),
        "gap_distribution": records(best[["constructor_name", "gap_pct", "year"]].round(3)),
        "grid_finish_matrix": {"grid": mat.index.tolist(), "finish": mat.columns.tolist(), "z": mat.values.tolist()},
        "by_grid": records(by_grid.round(4)), "spearman": corr,
    })


# ------------------------------------------------------------------ pit stops
@router.get("/pitstops")
def pitstops(season_from: int = 2012, season_to: int = 2024, constructors: str | None = None):
    p = _range(_pits(), season_from, season_to)
    if p.empty:
        raise HTTPException(400, "Pit-stop data is only available from 2011 onwards")
    v = p[p["valid"]]
    ids = _ids(constructors)
    top = ids or v.groupby("constructorId")["duration_s"].size().nlargest(10).index.tolist()
    vt = v[v["constructorId"].isin(top)]
    by_season = v.groupby("year").agg(median=("duration_s", "median"), p25=("duration_s", lambda s: s.quantile(.25)),
                                      p75=("duration_s", lambda s: s.quantile(.75)), stops=("duration_s", "size")).reset_index()
    stops_per_car = (p.groupby(["year", "raceId", "driverId"])["stop"].max().groupby("year").mean()
                     .rename("stops_per_car").reset_index())
    by_season = by_season.merge(stops_per_car, on="year")
    team = (vt.groupby("constructor_name")["duration_s"].agg(["median", "mean", "std", "size"]).reset_index()
            .sort_values("median"))
    team_season = vt.groupby(["year", "constructor_name"])["duration_s"].median().reset_index()
    lap_hist = p.groupby("lap").size().reset_index(name="stops")
    fastest = v.nsmallest(15, "duration_s")[["year", "race_name", "driver_name", "constructor_name", "lap", "duration_s"]]
    sample = vt[["constructor_name", "duration_s"]]
    if len(sample) > 6000:
        sample = sample.sample(6000, random_state=1)
    return clean({
        "by_season": records(by_season.round(3)), "by_team": records(team.round(3)),
        "team_season": records(team_season.round(3)), "lap_histogram": records(lap_hist),
        "fastest": records(fastest.round(3)), "distribution": records(sample.round(3)),
        "note": "Durations are pit-lane times (entry to exit) and exclude stops shorter than 10 s or longer than 60 s.",
    })


# ------------------------------------------------------------------ reliability
@router.get("/reliability")
def reliability(season_from: int = 2000, season_to: int = 2024, constructors: str | None = None, min_entries: int = 30):
    r = _range(_res(), season_from, season_to)
    ids = _ids(constructors)
    by_season = (r[r["dnf"]].groupby(["year", "status_group"]).size().unstack(fill_value=0))
    entries = r.groupby("year").size()
    rates = by_season.div(entries, axis=0).fillna(0)
    team = r.groupby(["constructorId", "constructor_name"]).agg(entries=("raceId", "size"), dnf_rate=("dnf", "mean")).reset_index()
    team = team[team["entries"] >= min_entries]
    if ids:
        team = team[team["constructorId"].isin(ids)]
    team = team.sort_values("dnf_rate")
    tsel = r[r["constructorId"].isin(team["constructorId"].head(12) if not ids else ids) & r["dnf"]]
    team_causes = tsel.groupby(["constructor_name", "status_group"]).size().unstack(fill_value=0)
    causes = r[r["dnf"]]["status"].value_counts().head(20)
    return clean({
        "seasons": rates.index.tolist(),
        "season_rates": [{"name": c, "values": rates[c].round(4).tolist()} for c in rates.columns],
        "teams": records(team.round(4)),
        "team_causes": {"teams": team_causes.index.tolist(),
                        "series": [{"name": c, "values": team_causes[c].tolist()} for c in team_causes.columns]},
        "top_causes": [{"status": k, "count": int(v)} for k, v in causes.items()],
        "overall_dnf_rate": float(r["dnf"].mean()),
    })


# ------------------------------------------------------------------ circuits
@router.get("/circuits")
def circuits(season_from: int = 2000, season_to: int = 2024):
    d = get_data()
    r = _range(_res(), season_from, season_to)
    g = r.groupby("circuitId")
    s = pd.DataFrame({
        "races": g["raceId"].nunique(),
        "dnf_rate": g["dnf"].mean(),
        "avg_abs_change": g.apply(lambda x: x.loc[x["finished"], "gained"].abs().mean()),
        "pole_to_win": g.apply(lambda x: (x.loc[x["grid"] == 1, "positionOrder"] == 1).mean()),
        "winner_avg_grid": g.apply(lambda x: x.loc[x["positionOrder"] == 1, "grid0"].mean()),
        "avg_fl_speed": g["fastestLapSpeed"].mean(),
    }).reset_index()
    s = s.merge(d.circuits[["circuitId", "name", "location", "country", "lat", "lng", "alt"]], on="circuitId")
    winners = (r[r["positionOrder"] == 1].groupby(["circuitId", "driver_name"]).size().reset_index(name="wins")
               .sort_values("wins", ascending=False).drop_duplicates("circuitId")
               .rename(columns={"driver_name": "top_winner", "wins": "top_winner_wins"}))
    s = s.merge(winners, on="circuitId", how="left").sort_values("races", ascending=False)
    return clean({"circuits": records(s.round(4))})


# ------------------------------------------------------------------ models
class PointsIn(BaseModel):
    driver_id: int | None = None
    constructor_id: int | None = None
    grid: int
    circuit_id: int
    season: int = 2024
    round: int = 10
    driver_form: float | None = None
    constructor_form: float | None = None


class WinnerIn(BaseModel):
    grids: dict[str, float | None]
    form: dict[str, dict[str, float | None]] | None = None


def _need(name: str) -> dict:
    try:
        return ml.model(name)
    except RuntimeError:
        raise HTTPException(503, "Models are still training. This takes about 20 seconds after the first start.")


@router.get("/models/status")
def models_status():
    return ml.status()


@router.post("/models/retrain")
def models_retrain():
    ml.start_training(force=True)
    return ml.status()


@router.get("/models/points")
def models_points():
    return _need("points")["report"]


@router.post("/models/points/predict")
def models_points_predict(body: PointsIn):
    _need("points")
    try:
        return ml.predict_points(body.driver_id, body.constructor_id, body.grid, body.circuit_id, body.season,
                                 body.round, body.driver_form, body.constructor_form)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/models/points/forms")
def models_points_forms(driver_id: int | None = None, constructor_id: int | None = None):
    f = _need("points")["forms"]
    return {"driver_form": f["driver"].get(driver_id, f["base"]) if driver_id else f["base"],
            "constructor_form": f["constructor"].get(constructor_id, f["base"]) if constructor_id else f["base"]}


@router.get("/models/winner")
def models_winner():
    return _need("winner")["report"]


@router.post("/models/winner/predict")
def models_winner_predict(body: WinnerIn):
    _need("winner")
    return ml.predict_winner(body.grids, body.form)


@router.get("/models/regression")
def models_regression():
    return _need("regression")["report"]


@router.get("/models/clustering")
def models_clustering(k: int = Query(4, ge=2, le=8), season_from: int = 2004, season_to: int = 2024,
                      min_races: int = 5, features: str = "avg_grid,avg_finish"):
    feats = tuple(f for f in features.split(",") if f in {"avg_grid", "avg_finish", "total_points", "points_rate"})
    if len(feats) < 2:
        raise HTTPException(400, "Pick at least two features")
    try:
        return ml.clustering(k, season_from, season_to, min_races, feats)
    except ValueError as e:
        raise HTTPException(400, str(e))
