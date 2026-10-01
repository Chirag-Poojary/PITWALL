"""Public fan endpoints: drivers, constructors, standings, calendar, feed and profile."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import db, live
from .auth import public_user, require_user
from .data import get_data

router = APIRouter(prefix="/api", tags=["fan"])

SESSION_LENGTH = {"practice": 60, "qualifying": 60, "sprint": 60, "race": 120}


@router.get("/meta")
def meta():
    return get_data().meta()


@router.get("/drivers")
def drivers(q: str | None = None, nationality: str | None = None, decade: int | None = None,
            season: int | None = None, champions: bool = False, sort: str = "points", order: str = "desc",
            limit: int = Query(60, le=1000), offset: int = 0):
    return get_data().driver_list(q, nationality, decade, season, champions, sort, order, limit, offset)


@router.get("/drivers/{driver_id}")
def driver(driver_id: int):
    d = get_data().driver_detail(driver_id)
    if not d:
        raise HTTPException(404, "Driver not found")
    return d


@router.get("/constructors")
def constructors(q: str | None = None, nationality: str | None = None, decade: int | None = None,
                 season: int | None = None, champions: bool = False, sort: str = "points", order: str = "desc",
                 limit: int = Query(60, le=1000), offset: int = 0):
    return get_data().constructor_list(q, nationality, decade, season, champions, sort, order, limit, offset)


@router.get("/constructors/{cid}")
def constructor(cid: int):
    d = get_data().constructor_detail(cid)
    if not d:
        raise HTTPException(404, "Constructor not found")
    return d


@router.get("/standings/drivers")
def standings_drivers(season: int):
    return get_data().driver_standings_for(season)


@router.get("/standings/constructors")
def standings_constructors(season: int):
    return get_data().constructor_standings_for(season)


@router.get("/seasons/{year}/calendar")
def calendar(year: int):
    return get_data().season_calendar(year)


# ---------------------------------------------------------------- schedule
def _dataset_schedule() -> dict:
    """Fallback calendar built from races.csv (latest season in the dataset)."""
    d = get_data()
    year = d.latest_season
    r = d.races[d.races["year"] == year].sort_values("round")
    circ = d.circuits.set_index("circuitId")["circuitRef"]
    out = []
    for _, x in r.iterrows():
        def iso(dc, tc):
            if pd.isna(x.get(dc)):
                return None
            return f"{x[dc]}T{x[tc] if not pd.isna(x.get(tc)) else '12:00:00'}Z"
        sessions = []
        for dc, tc, name, kind in [("fp1_date", "fp1_time", "Practice 1", "practice"),
                                   ("fp2_date", "fp2_time", "Practice 2", "practice"),
                                   ("fp3_date", "fp3_time", "Practice 3", "practice"),
                                   ("quali_date", "quali_time", "Qualifying", "qualifying"),
                                   ("sprint_date", "sprint_time", "Sprint", "sprint")]:
            s = iso(dc, tc)
            if s:
                sessions.append({"name": name, "kind": kind, "start": s})
        race_start = f"{x['date'].strftime('%Y-%m-%d')}T{x['time'] if not pd.isna(x['time']) else '12:00:00'}Z"
        sessions.append({"name": "Grand Prix", "kind": "race", "start": race_start})
        sessions.sort(key=lambda s: s["start"])
        out.append({
            "season": year, "round": int(x["round"]), "race_name": x["race_name"],
            "circuit_ref": circ.get(x["circuitId"]), "circuit_name": x["circuit_name"],
            "locality": x["location"], "country": x["country"], "lat": float(x["lat"]), "lng": float(x["lng"]),
            "date": x["date"].strftime("%Y-%m-%d"), "start": race_start,
            "sprint_weekend": any(s["kind"] == "sprint" for s in sessions), "sessions": sessions, "url": x["url"],
        })
    return {"season": year, "races": out}


def get_schedule() -> tuple[dict, str]:
    s = live.schedule()
    if s and s["races"]:
        return s, "live"
    return _dataset_schedule(), "dataset"


def _parse(s: str | None):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


@router.get("/schedule")
def schedule():
    sched, source = get_schedule()
    now = datetime.now(timezone.utc)
    for r in sched["races"]:
        start = _parse(r["sessions"][0]["start"]) if r["sessions"] else _parse(r["start"])
        end = _parse(r["start"]) + timedelta(minutes=150)
        r["status"] = "completed" if now > end else ("live" if start and now >= start - timedelta(hours=1) else "upcoming")
    return {"source": source, **sched}


# ---------------------------------------------------------------- catalog
@router.get("/catalog")
def catalog():
    """Driver / constructor / Grand Prix lists for the profile pickers."""
    d = get_data()
    base = d.grid_for_season(d.latest_season)
    drivers = {x["ref"]: x for x in base["drivers"]}
    cons = {x["ref"]: x for x in base["constructors"]}
    source = "dataset"
    ls = live.driver_standings()
    if ls:
        source = "live"
        for s in ls:
            known = d.driver_by_ref(s["driver_ref"])
            drivers[s["driver_ref"]] = {"ref": s["driver_ref"], "id": known["driverId"] if known else None,
                                        "name": s["name"], "code": s["code"], "team": s["team"], "current": True}
    lc = live.constructor_standings()
    if lc:
        for s in lc:
            known = d.constructor_by_ref(s["team_ref"])
            cons[s["team_ref"]] = {"ref": s["team_ref"], "id": known["constructorId"] if known else None,
                                   "name": s["name"], "current": True}
    sched, _ = get_schedule()
    events = [{"ref": r["circuit_ref"], "name": r["race_name"], "country": r["country"]} for r in sched["races"]]
    # also allow searching any historical driver/team
    return {"source": source, "drivers": sorted(drivers.values(), key=lambda x: (not x.get("current"), x["name"])),
            "constructors": sorted(cons.values(), key=lambda x: (not x.get("current"), x["name"])), "events": events}


# ---------------------------------------------------------------- profile
class PrefsIn(BaseModel):
    fav_drivers: list[str] | None = None
    fav_constructors: list[str] | None = None
    followed_sessions: list[str] | None = None
    followed_events: list[str] | None = None
    onboarded: bool | None = None


class ProfileIn(BaseModel):
    name: str | None = None


@router.get("/me/profile")
def get_profile(u=Depends(require_user)):
    return {"user": public_user(u), "preferences": db.get_prefs(u["id"])}


@router.put("/me/profile")
def put_profile(body: ProfileIn, u=Depends(require_user)):
    if body.name and len(body.name.strip()) >= 2:
        db.update_user(u["id"], name=body.name.strip())
    return {"user": public_user(db.get_user(u["id"])), "preferences": db.get_prefs(u["id"])}


@router.put("/me/preferences")
def put_prefs(body: PrefsIn, u=Depends(require_user)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if "followed_sessions" in data:
        data["followed_sessions"] = [s for s in data["followed_sessions"] if s in SESSION_LENGTH]
    return db.save_prefs(u["id"], data)


# ---------------------------------------------------------------- feed
@router.get("/me/feed")
def feed(u=Depends(require_user)):
    d = get_data()
    prefs = db.get_prefs(u["id"])
    sched, source = get_schedule()
    now = datetime.now(timezone.utc)
    kinds = set(prefs["followed_sessions"] or SESSION_LENGTH.keys())
    events = set(prefs["followed_events"])

    sessions = []
    for r in sched["races"]:
        if events and r["circuit_ref"] not in events:
            continue
        for s in r["sessions"]:
            if s["kind"] not in kinds or not s["start"]:
                continue
            st = _parse(s["start"])
            en = st + timedelta(minutes=SESSION_LENGTH[s["kind"]])
            if en < now:
                continue
            sessions.append({**s, "end": en.isoformat().replace("+00:00", "Z"),
                             "live": st <= now <= en, "race_name": r["race_name"], "round": r["round"],
                             "country": r["country"], "locality": r["locality"], "circuit_name": r["circuit_name"],
                             "circuit_ref": r["circuit_ref"]})
    sessions.sort(key=lambda s: s["start"])
    next_race = next((r for r in sched["races"] if _parse(r["start"]) + timedelta(hours=2) >= now
                      and (not events or r["circuit_ref"] in events)), None)

    # standings (live if possible, else the dataset's last season)
    ds, cs = live.driver_standings(), live.constructor_standings()
    standings_source = "live"
    if not ds:
        standings_source = "dataset"
        ds = [{"position": x["position"], "points": x["points"], "wins": x["wins"], "name": x["name"], "code": x["code"],
               "team": x["constructor_name"], "driver_ref": d.drivers.set_index("driverId").loc[x["driverId"], "driverRef"]}
              for x in d.driver_standings_for(d.latest_season)]
        cons_ref = d.constructors.set_index("constructorId")["constructorRef"]
        cs = [{"position": x["position"], "points": x["points"], "wins": x["wins"], "name": x["name"],
               "team_ref": cons_ref.get(x["constructorId"])} for x in d.constructor_standings_for(d.latest_season)]

    fav_d = []
    for ref in prefs["fav_drivers"]:
        hist = d.driver_by_ref(ref)
        cur = next((s for s in ds if s.get("driver_ref") == ref), None)
        fav_d.append({"ref": ref, "career": {k: hist[k] for k in ["driverId", "name", "code", "nationality", "starts",
                                                                   "wins", "podiums", "poles", "titles", "points"]} if hist else None,
                      "current": cur})
    fav_c = []
    for ref in prefs["fav_constructors"]:
        hist = d.constructor_by_ref(ref)
        cur = next((s for s in cs if s.get("team_ref") == ref), None)
        fav_c.append({"ref": ref, "career": {k: hist[k] for k in ["constructorId", "name", "nationality", "races", "wins",
                                                                   "podiums", "titles", "points"]} if hist else None,
                      "current": cur})

    last = live.last_results() if source == "live" else None
    return {
        "source": source, "standings_source": standings_source, "season": sched["season"],
        "preferences": prefs, "next_race": next_race, "upcoming_sessions": sessions[:12],
        "fav_drivers": fav_d, "fav_constructors": fav_c,
        "driver_standings": ds[:10], "constructor_standings": cs[:10], "last_race": last,
        "server_time": now.isoformat(),
    }
