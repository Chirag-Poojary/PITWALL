"""Live season data from the Jolpica-F1 API (the community successor of Ergast).

The CSV dataset stops at the end of 2024, so the personalised feed asks Jolpica
for the current calendar and standings. Responses are cached in memory. If the
API cannot be reached, callers get `None` and fall back to the dataset.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

import httpx

BASE = os.getenv("F1_LIVE_API", "https://api.jolpi.ca/ergast/f1")
TTL = int(os.getenv("F1_LIVE_TTL", "1800"))  # seconds
_cache: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()

SESSION_KEYS = [
    ("FirstPractice", "Practice 1", "practice"),
    ("SecondPractice", "Practice 2", "practice"),
    ("ThirdPractice", "Practice 3", "practice"),
    ("SprintQualifying", "Sprint Qualifying", "sprint"),
    ("SprintShootout", "Sprint Shootout", "sprint"),
    ("Sprint", "Sprint", "sprint"),
    ("Qualifying", "Qualifying", "qualifying"),
]


def _get(path: str):
    now = time.time()
    with _lock:
        hit = _cache.get(path)
        if hit and now - hit[0] < TTL:
            return hit[1]
    try:
        r = httpx.get(f"{BASE}/{path}", timeout=8.0, params={"limit": 100})
        r.raise_for_status()
        data = r.json()["MRData"]
    except Exception:
        # serve stale data if we have it
        return hit[1] if hit else None
    with _lock:
        _cache[path] = (now, data)
    return data


def _iso(date: str | None, t: str | None) -> str | None:
    if not date:
        return None
    t = (t or "12:00:00Z").replace("Z", "")
    return f"{date}T{t}Z"


def schedule(season: str = "current") -> dict | None:
    data = _get(f"{season}.json")
    if not data:
        return None
    races = data["RaceTable"]["Races"]
    out = []
    for r in races:
        sessions = []
        for key, label, kind in SESSION_KEYS:
            if key in r:
                sessions.append({"name": label, "kind": kind, "start": _iso(r[key].get("date"), r[key].get("time"))})
        sessions.append({"name": "Grand Prix", "kind": "race", "start": _iso(r.get("date"), r.get("time"))})
        sessions.sort(key=lambda s: s["start"] or "")
        c = r["Circuit"]
        out.append({
            "season": int(r["season"]), "round": int(r["round"]), "race_name": r["raceName"],
            "circuit_ref": c["circuitId"], "circuit_name": c["circuitName"],
            "locality": c["Location"].get("locality"), "country": c["Location"].get("country"),
            "lat": float(c["Location"]["lat"]), "lng": float(c["Location"]["long"]),
            "date": r.get("date"), "start": _iso(r.get("date"), r.get("time")),
            "sprint_weekend": any(s["kind"] == "sprint" for s in sessions),
            "sessions": sessions, "url": r.get("url"),
        })
    return {"season": int(data["RaceTable"].get("season", 0) or (races[0]["season"] if races else 0)), "races": out}


def driver_standings(season: str = "current") -> list | None:
    data = _get(f"{season}/driverStandings.json")
    if not data:
        return None
    lists = data["StandingsTable"]["StandingsLists"]
    if not lists:
        return []
    out = []
    for s in lists[0]["DriverStandings"]:
        d = s["Driver"]
        team = s["Constructors"][-1] if s.get("Constructors") else {}
        out.append({
            "position": int(s["position"]) if str(s.get("position", "")).isdigit() else 0,
            "points": float(s["points"]), "wins": int(s["wins"]), "driver_ref": d["driverId"],
            "code": d.get("code"), "name": f"{d['givenName']} {d['familyName']}", "nationality": d.get("nationality"),
            "number": d.get("permanentNumber"), "team": team.get("name"), "team_ref": team.get("constructorId"),
            "round": int(lists[0].get("round", 0)),
        })
    return out


def constructor_standings(season: str = "current") -> list | None:
    data = _get(f"{season}/constructorStandings.json")
    if not data:
        return None
    lists = data["StandingsTable"]["StandingsLists"]
    if not lists:
        return []
    return [{
        "position": int(s["position"]) if str(s.get("position", "")).isdigit() else 0,
        "points": float(s["points"]), "wins": int(s["wins"]),
        "team_ref": s["Constructor"]["constructorId"], "name": s["Constructor"]["name"],
        "nationality": s["Constructor"].get("nationality"), "round": int(lists[0].get("round", 0)),
    } for s in lists[0]["ConstructorStandings"]]


def last_results(season: str = "current") -> dict | None:
    data = _get(f"{season}/last/results.json")
    if not data:
        return None
    races = data["RaceTable"]["Races"]
    if not races:
        return {}
    r = races[0]
    return {
        "race_name": r["raceName"], "round": int(r["round"]), "date": r.get("date"),
        "results": [{
            "position": res.get("positionText"), "driver_ref": res["Driver"]["driverId"],
            "name": f"{res['Driver']['givenName']} {res['Driver']['familyName']}", "code": res["Driver"].get("code"),
            "team": res["Constructor"]["name"], "team_ref": res["Constructor"]["constructorId"],
            "points": float(res.get("points", 0)), "grid": int(res.get("grid") or 0), "status": res.get("status"),
        } for res in r["Results"]],
    }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
