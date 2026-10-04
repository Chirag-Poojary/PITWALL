"""Loads F1 dataset directly from Supabase Cloud PostgreSQL and keeps precomputed tables in memory.

100% powered by Supabase Cloud Database. No local CSV files or SQLite instances.
"""
from __future__ import annotations

import io
import json
import logging
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger("pitwall.data")

_LAPS_RE = re.compile(r"^\+\d+ Laps?$")


def records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN -> None, numpy -> python)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def clean(obj: Any) -> Any:
    """Recursively convert numpy / NaN values into JSON-safe python values."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if (obj is None or np.isnan(obj)) else float(obj)
    if isinstance(obj, np.ndarray):
        return clean(obj.tolist())
    if obj is pd.NaT:
        return None
    return obj


class F1Data:
    """Holds all active in-memory F1 tables, loaded directly from Supabase Cloud Database."""

    def __init__(self) -> None:
        self._lap_times: pd.DataFrame | None = None
        self._f1: pd.DataFrame | None = None
        self._qualifying: pd.DataFrame | None = None
        self._pit_stops: pd.DataFrame | None = None
        self._load_from_supabase()
        self._prepare()

    # ------------------------------------------------------------------ Load from Supabase
    def _load_from_supabase(self) -> None:
        from . import db

        url, key = db.get_supabase_credentials()
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Range-Unit": "items",
            "Accept": "text/csv",
        }

        with db.get_http_client(timeout=25.0, max_connections=40) as client:
            def get_csv(path: str, rng: str | None = None, params: str | None = None) -> bytes:
                h = dict(headers)
                if rng:
                    h["Range"] = rng
                q = f"{url}/rest/v1/{path}"
                if params:
                    q += f"?{params}"
                r = client.get(q, headers=h)
                return r.content if r.status_code in (200, 206) else b""

            with ThreadPoolExecutor(max_workers=36) as pool:
                # 1. Reference tables
                f_circuits = pool.submit(get_csv, "circuits", "0-999")
                f_constructors = pool.submit(get_csv, "constructors", "0-999")
                f_drivers = pool.submit(get_csv, "drivers", "0-999")
                f_races_1 = pool.submit(get_csv, "races", "0-999")
                f_races_2 = pool.submit(get_csv, "races", "1000-1999")
                f_status = pool.submit(get_csv, "race_statuses", "0-999")
                f_sprint = pool.submit(get_csv, "sprint_results", "0-999")

                # 2. Race results (all 27 chunks in parallel)
                res_chunks = [(i, min(i + 999, 26758)) for i in range(0, 26759, 1000)]
                f_results = [pool.submit(get_csv, "race_results", f"{r[0]}-{r[1]}") for r in res_chunks]

                # Wait for races to compute season finale race IDs for standings
                r1_content = f_races_1.result()
                r2_content = f_races_2.result()
                df_races_pre = pd.concat(
                    [
                        pd.read_csv(io.BytesIO(r1_content), encoding="utf-8", na_values=["\\N", "\\\\N"]),
                        pd.read_csv(io.BytesIO(r2_content), encoding="utf-8", na_values=["\\N", "\\\\N"]),
                    ],
                    ignore_index=True,
                )
                last_rounds = df_races_pre.groupby("year")["round"].idxmax()
                final_race_ids = df_races_pre.loc[last_rounds, "race_id"].tolist()
                race_id_filter = "in.(" + ",".join(str(i) for i in final_race_ids) + ")"

                # 3. Final standings queries
                ds_ranges = ["0-999", "1000-1999", "2000-2999", "3000-3999"]
                f_ds = [pool.submit(get_csv, "driver_standings", rng, f"race_id={race_id_filter}") for rng in ds_ranges]
                f_cs = pool.submit(get_csv, "constructor_standings", "0-999", f"race_id={race_id_filter}")

                # 4. Assemble DataFrames
                self.circuits = pd.read_csv(io.BytesIO(f_circuits.result()), encoding="utf-8", na_values=["\\N", "\\\\N"]).rename(
                    columns={"circuit_id": "circuitId", "circuit_ref": "circuitRef"}
                )
                self.constructors = pd.read_csv(io.BytesIO(f_constructors.result()), encoding="utf-8", na_values=["\\N", "\\\\N"]).rename(
                    columns={"constructor_id": "constructorId", "constructor_ref": "constructorRef"}
                )
                self.drivers = pd.read_csv(io.BytesIO(f_drivers.result()), encoding="utf-8", na_values=["\\N", "\\\\N"]).rename(
                    columns={"driver_id": "driverId", "driver_ref": "driverRef", "driver_number": "number"}
                )
                self.races = df_races_pre.rename(
                    columns={"race_id": "raceId", "circuit_id": "circuitId", "race_date": "date", "race_time": "time"}
                )
                self.status = pd.read_csv(io.BytesIO(f_status.result()), encoding="utf-8", na_values=["\\N", "\\\\N"]).rename(
                    columns={"status_id": "statusId", "status_name": "status"}
                )
                self.sprint_results = pd.read_csv(io.BytesIO(f_sprint.result()), encoding="utf-8", na_values=["\\N", "\\\\N"]).rename(
                    columns={
                        "sprint_result_id": "resultId",
                        "race_id": "raceId",
                        "driver_id": "driverId",
                        "constructor_id": "constructorId",
                        "driver_number": "number",
                        "position_text": "positionText",
                        "position_order": "positionOrder",
                        "fastest_lap": "fastestLap",
                        "fastest_lap_time": "fastestLapTime",
                        "status_id": "statusId",
                    }
                )

                raw_results = [f.result() for f in f_results]
                self.results = pd.concat(
                    [pd.read_csv(io.BytesIO(c), encoding="utf-8", na_values=["\\N", "\\\\N"]) for c in raw_results if len(c) > 20],
                    ignore_index=True,
                ).rename(
                    columns={
                        "result_id": "resultId",
                        "race_id": "raceId",
                        "driver_id": "driverId",
                        "constructor_id": "constructorId",
                        "driver_number": "number",
                        "position_text": "positionText",
                        "position_order": "positionOrder",
                        "race_time": "time",
                        "fastest_lap": "fastestLap",
                        "fastest_lap_rank": "rank",
                        "fastest_lap_time": "fastestLapTime",
                        "fastest_lap_speed": "fastestLapSpeed",
                        "status_id": "statusId",
                    }
                )

                raw_ds = [f.result() for f in f_ds]
                self.driver_standings = pd.concat(
                    [pd.read_csv(io.BytesIO(c), encoding="utf-8", na_values=["\\N", "\\\\N"]) for c in raw_ds if len(c) > 20],
                    ignore_index=True,
                ).dropna(subset=["driver_standings_id"]).rename(
                    columns={
                        "driver_standings_id": "driverStandingsId",
                        "race_id": "raceId",
                        "driver_id": "driverId",
                        "position_text": "positionText",
                    }
                )

                self.constructor_standings = pd.read_csv(
                    io.BytesIO(f_cs.result()), encoding="utf-8", na_values=["\\N", "\\\\N"]
                ).rename(
                    columns={
                        "constructor_standings_id": "constructorStandingsId",
                        "race_id": "raceId",
                        "constructor_id": "constructorId",
                        "position_text": "positionText",
                    }
                )

    # ------------------------------------------------------------------ Setup & Precomputation
    def _prepare(self) -> None:
        d = self.drivers
        d["name"] = d["forename"].str.strip() + " " + d["surname"].str.strip()
        d["dob"] = pd.to_datetime(d["dob"], errors="coerce")
        self.constructors["name"] = self.constructors["name"].str.replace("&amp;", "&", regex=False)

        r = self.races.rename(columns={"name": "race_name"})
        r["date"] = pd.to_datetime(r["date"], errors="coerce")
        r = r.merge(
            self.circuits[["circuitId", "name", "location", "country", "lat", "lng", "alt"]].rename(
                columns={"name": "circuit_name"}
            ),
            on="circuitId",
            how="left",
        )
        self.races = r

        st = self.status.set_index("statusId")["status"]
        res = self.results.copy()
        res["status"] = res["statusId"].map(st)
        res["finished"] = res["status"].eq("Finished") | res["status"].fillna("").str.match(_LAPS_RE)
        res["dnf"] = ~res["finished"]
        res["fastestLapSpeed"] = pd.to_numeric(res["fastestLapSpeed"], errors="coerce")
        res = res.merge(
            r[["raceId", "year", "round", "race_name", "date", "circuitId", "circuit_name", "country"]],
            on="raceId",
            how="left",
        )
        res = res.merge(
            d[["driverId", "name", "code", "driverRef", "nationality"]].rename(
                columns={"name": "driver_name", "nationality": "driver_nationality"}
            ),
            on="driverId",
            how="left",
        )
        res = res.merge(
            self.constructors[["constructorId", "name", "constructorRef"]].rename(
                columns={"name": "constructor_name"}
            ),
            on="constructorId",
            how="left",
        )
        self.res = res

        # Standings for final race of each season
        ds = self.driver_standings.merge(r[["raceId", "year", "round"]], on="raceId")
        last_round = ds.groupby("year")["round"].transform("max")
        self.final_driver_st = ds[ds["round"] == last_round].copy()

        cs = self.constructor_standings.merge(r[["raceId", "year", "round"]], on="raceId")
        last_round_c = cs.groupby("year")["round"].transform("max")
        self.final_cons_st = cs[cs["round"] == last_round_c].copy()

        self.driver_titles = (
            self.final_driver_st[self.final_driver_st["position"] == 1]
            .groupby("driverId")["year"]
            .apply(sorted)
            .to_dict()
        )
        self.cons_titles = (
            self.final_cons_st[self.final_cons_st["position"] == 1]
            .groupby("constructorId")["year"]
            .apply(sorted)
            .to_dict()
        )
        self.seasons = sorted(int(y) for y in r["year"].dropna().unique() if y in set(res["year"].unique()))
        self.latest_season = max(self.seasons)
        self._driver_summary = self._build_driver_summary()
        self._cons_summary = self._build_constructor_summary()

    @property
    def lap_times(self) -> pd.DataFrame:
        """Returns empty DataFrame schema since lap times are loaded on-demand from Supabase per race."""
        if self._lap_times is None:
            self._lap_times = pd.DataFrame(columns=["raceId", "driverId", "lap", "position", "time", "milliseconds"])
        return self._lap_times

    def lap_times_for_race(self, race_id: int) -> pd.DataFrame:
        """Fetches lap times for a single race directly from Supabase Cloud Database."""
        from . import db

        rows = db.fetch_lap_times_for_race(race_id)
        if rows:
            df = pd.DataFrame(rows)
            return df.rename(columns={"race_id": "raceId", "driver_id": "driverId", "lap_time_str": "time"})
        return pd.DataFrame(columns=["raceId", "driverId", "lap", "position", "time", "milliseconds"])

    def race_ids_with_laps(self) -> set[int]:
        """Set of raceIds that have lap-by-lap records in Supabase (1996 onwards)."""
        return set(self.races[self.races["year"] >= 1996]["raceId"].unique())

    @property
    def qualifying(self) -> pd.DataFrame:
        """Loaded lazily on first access from Supabase."""
        if self._qualifying is None:
            from . import db

            rows = db.fetch_all_rows_parallel("qualifying_results", "*", 10494)
            self._qualifying = pd.DataFrame(rows).rename(
                columns={
                    "qualify_id": "qualifyId",
                    "race_id": "raceId",
                    "driver_id": "driverId",
                    "constructor_id": "constructorId",
                    "driver_number": "number",
                }
            )
        return self._qualifying

    @property
    def pit_stops(self) -> pd.DataFrame:
        """Loaded lazily on first access from Supabase."""
        if self._pit_stops is None:
            from . import db

            rows = db.fetch_all_rows_parallel("pit_stops", "*", 11371)
            self._pit_stops = pd.DataFrame(rows).rename(
                columns={
                    "race_id": "raceId",
                    "driver_id": "driverId",
                    "stop_number": "stop",
                    "stop_time": "time",
                    "stop_duration": "duration",
                }
            )
        return self._pit_stops

    @property
    def f1(self) -> pd.DataFrame:
        """The dataset used by ML models (loaded directly from Supabase view v_f1_ml_dataset)."""
        if self._f1 is None:
            from . import db

            rows = db.fetch_ml_dataset(min_season=2004)
            if not rows:
                raise RuntimeError("Failed to retrieve ML dataset from Supabase view 'v_f1_ml_dataset'.")

            df = pd.DataFrame(rows)
            rename_cols = {
                "result_id": "resultId",
                "race_id": "raceId",
                "driver_id": "driverId",
                "constructor_id": "constructorId",
                "circuit_id": "circuitId",
                "driver_number": "driver_number",
                "nationality_driver": "nationality_driver",
                "nationality_constructor": "nationality_constructor",
                "driver_ref": "driverRef",
                "constructor_ref": "constructorRef",
                "circuit_ref": "circuitRef",
                "position_text": "positionText",
                "position_order": "positionOrder",
                "fastest_lap": "fastestLap",
                "fastest_lap_time": "fastestLapTime",
                "fastest_lap_speed": "fastestLapSpeed",
                "status_id": "statusId",
            }
            df = df.rename(columns=rename_cols)
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["dob"] = pd.to_datetime(df["dob"], errors="coerce")
            for c in ["grid", "laps", "fastestLapSpeed", "points", "positionOrder"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            self._f1 = df
        return self._f1

    # -------------------------------------------------------------- Summaries
    def _team_by_season(self, key: str) -> pd.DataFrame:
        """Main team (most entries) for each driver in each season."""
        g = (
            self.res.groupby([key, "year", "constructorId", "constructor_name"])
            .size()
            .reset_index(name="n")
            .sort_values("n", ascending=False)
            .drop_duplicates([key, "year"])
        )
        return g

    def _build_driver_summary(self) -> pd.DataFrame:
        res = self.res
        g = res.groupby("driverId")
        s = pd.DataFrame(
            {
                "starts": g.size(),
                "wins": g["positionOrder"].apply(lambda x: int((x == 1).sum())),
                "podiums": g["positionOrder"].apply(lambda x: int((x <= 3).sum())),
                "poles": g["grid"].apply(lambda x: int((x == 1).sum())),
                "points": g["points"].sum(),
                "dnfs": g["dnf"].sum(),
                "fastest_laps": g["rank"].apply(lambda x: int((pd.to_numeric(x, errors="coerce") == 1).sum())),
                "best_finish": g["positionOrder"].min(),
                "first_season": g["year"].min(),
                "last_season": g["year"].max(),
            }
        ).reset_index()
        last_team = (
            res.sort_values("date")
            .groupby("driverId")
            .tail(1)[["driverId", "constructorId", "constructor_name"]]
            .rename(columns={"constructorId": "last_team_id", "constructor_name": "last_team"})
        )
        teams = res.groupby("driverId")["constructor_name"].apply(lambda x: list(dict.fromkeys(x))).rename("teams")
        out = (
            self.drivers[
                ["driverId", "driverRef", "number", "code", "name", "forename", "surname", "dob", "nationality", "url"]
            ]
            .merge(s, on="driverId", how="inner")
            .merge(last_team, on="driverId", how="left")
            .merge(teams, on="driverId", how="left")
        )
        out["titles"] = out["driverId"].map(lambda i: len(self.driver_titles.get(i, [])))
        out["title_years"] = out["driverId"].map(lambda i: self.driver_titles.get(i, []))
        out["win_rate"] = (out["wins"] / out["starts"]).round(4)
        out["podium_rate"] = (out["podiums"] / out["starts"]).round(4)
        out["dob"] = out["dob"].dt.strftime("%Y-%m-%d")
        return out

    def _build_constructor_summary(self) -> pd.DataFrame:
        res = self.res
        g = res.groupby("constructorId")
        s = pd.DataFrame(
            {
                "entries": g.size(),
                "races": g["raceId"].nunique(),
                "wins": g["positionOrder"].apply(lambda x: int((x == 1).sum())),
                "podiums": g["positionOrder"].apply(lambda x: int((x <= 3).sum())),
                "poles": g["grid"].apply(lambda x: int((x == 1).sum())),
                "points": g["points"].sum(),
                "dnfs": g["dnf"].sum(),
                "drivers_count": g["driverId"].nunique(),
                "first_season": g["year"].min(),
                "last_season": g["year"].max(),
            }
        ).reset_index()
        out = self.constructors[["constructorId", "constructorRef", "name", "nationality", "url"]].merge(
            s, on="constructorId"
        )
        out["titles"] = out["constructorId"].map(lambda i: len(self.cons_titles.get(i, [])))
        out["title_years"] = out["constructorId"].map(lambda i: self.cons_titles.get(i, []))
        out["win_rate"] = (out["wins"] / out["races"]).round(4)
        out["dnf_rate"] = (out["dnfs"] / out["entries"]).round(4)
        return out

    # ------------------------------------------------------------ Fan Queries
    def driver_list(
        self,
        q=None,
        nationality=None,
        decade=None,
        season=None,
        champions=False,
        sort="points",
        order="desc",
        limit=60,
        offset=0,
    ) -> dict:
        df = self._driver_summary
        if q:
            ql = q.lower()
            df = df[df["name"].str.lower().str.contains(ql, regex=False) | df["code"].fillna("").str.lower().eq(ql)]
        if nationality:
            df = df[df["nationality"] == nationality]
        if decade:
            d0 = int(decade)
            df = df[(df["first_season"] <= d0 + 9) & (df["last_season"] >= d0)]
        if season:
            ids = self.res.loc[self.res["year"] == int(season), "driverId"].unique()
            df = df[df["driverId"].isin(ids)]
        if champions:
            df = df[df["titles"] > 0]
        if sort not in df.columns:
            sort = "points"
        df = df.sort_values([sort, "wins"], ascending=[order == "asc", False])
        total = len(df)
        page = df.iloc[offset : offset + limit]
        cols = [
            "driverId",
            "driverRef",
            "code",
            "number",
            "name",
            "nationality",
            "dob",
            "starts",
            "wins",
            "podiums",
            "poles",
            "points",
            "titles",
            "first_season",
            "last_season",
            "last_team",
            "last_team_id",
        ]
        return {"total": total, "items": records(page[cols])}

    def driver_detail(self, driver_id: int) -> dict | None:
        row = self._driver_summary[self._driver_summary["driverId"] == driver_id]
        if row.empty:
            return None
        info = records(row)[0]
        res = self.res[self.res["driverId"] == driver_id].sort_values("date")
        teams = self._team_by_season("driverId")
        teams = teams[teams["driverId"] == driver_id]
        season = (
            res.groupby("year")
            .agg(
                races=("raceId", "size"),
                points=("points", "sum"),
                wins=("positionOrder", lambda x: int((x == 1).sum())),
                podiums=("positionOrder", lambda x: int((x <= 3).sum())),
                poles=("grid", lambda x: int((x == 1).sum())),
                avg_grid=("grid", lambda x: x.replace(0, np.nan).mean()),
                avg_finish=("positionOrder", "mean"),
                dnfs=("dnf", "sum"),
            )
            .reset_index()
        )
        champ = self.final_driver_st[self.final_driver_st["driverId"] == driver_id][["year", "position"]].rename(
            columns={"position": "championship_pos"}
        )
        season = season.merge(champ, on="year", how="left").merge(
            teams[["year", "constructor_name", "constructorId"]], on="year", how="left"
        )
        season["avg_grid"] = season["avg_grid"].round(2)
        season["avg_finish"] = season["avg_finish"].round(2)

        fin = res[res["finished"]]["positionOrder"].clip(upper=20).value_counts().sort_index()
        dist = [{"position": int(k), "count": int(v)} for k, v in fin.items()]
        status = res.loc[res["dnf"], "status"].value_counts().head(8)
        recent = res.tail(10)[
            [
                "raceId",
                "year",
                "round",
                "race_name",
                "date",
                "constructor_name",
                "grid",
                "positionText",
                "points",
                "status",
            ]
        ].iloc[::-1]

        stints = []
        for _, t in teams.sort_values("year").iterrows():
            if stints and stints[-1]["constructorId"] == t["constructorId"] and stints[-1]["to"] == t["year"] - 1:
                stints[-1]["to"] = int(t["year"])
            else:
                stints.append(
                    {
                        "constructorId": int(t["constructorId"]),
                        "team": t["constructor_name"],
                        "from": int(t["year"]),
                        "to": int(t["year"]),
                    }
                )
        age = None
        if info.get("dob"):
            age = int((pd.Timestamp.today() - pd.Timestamp(info["dob"])).days // 365.25)
        return clean(
            {
                "driver": info,
                "age": age,
                "seasons": records(season),
                "finish_distribution": dist,
                "dnf_causes": [{"status": k, "count": int(v)} for k, v in status.items()],
                "recent_results": records(recent),
                "stints": stints,
            }
        )

    def constructor_list(
        self,
        q=None,
        nationality=None,
        decade=None,
        season=None,
        champions=False,
        sort="points",
        order="desc",
        limit=60,
        offset=0,
    ) -> dict:
        df = self._cons_summary
        if q:
            df = df[df["name"].str.lower().str.contains(q.lower(), regex=False)]
        if nationality:
            df = df[df["nationality"] == nationality]
        if decade:
            d0 = int(decade)
            df = df[(df["first_season"] <= d0 + 9) & (df["last_season"] >= d0)]
        if season:
            ids = self.res.loc[self.res["year"] == int(season), "constructorId"].unique()
            df = df[df["constructorId"].isin(ids)]
        if champions:
            df = df[df["titles"] > 0]
        if sort not in df.columns:
            sort = "points"
        df = df.sort_values([sort, "wins"], ascending=[order == "asc", False])
        cols = [
            "constructorId",
            "constructorRef",
            "name",
            "nationality",
            "races",
            "wins",
            "podiums",
            "poles",
            "points",
            "titles",
            "first_season",
            "last_season",
            "drivers_count",
        ]
        return {"total": len(df), "items": records(df.iloc[offset : offset + limit][cols])}

    def constructor_detail(self, cid: int) -> dict | None:
        row = self._cons_summary[self._cons_summary["constructorId"] == cid]
        if row.empty:
            return None
        info = records(row)[0]
        res = self.res[self.res["constructorId"] == cid]
        season = (
            res.groupby("year")
            .agg(
                races=("raceId", "nunique"),
                points=("points", "sum"),
                wins=("positionOrder", lambda x: int((x == 1).sum())),
                podiums=("positionOrder", lambda x: int((x <= 3).sum())),
                poles=("grid", lambda x: int((x == 1).sum())),
                dnf_rate=("dnf", "mean"),
            )
            .reset_index()
        )
        champ = self.final_cons_st[self.final_cons_st["constructorId"] == cid][["year", "position"]].rename(
            columns={"position": "championship_pos"}
        )
        season = season.merge(champ, on="year", how="left")
        season["dnf_rate"] = season["dnf_rate"].round(3)
        drv = (
            res.groupby(["driverId", "driver_name"])
            .agg(
                races=("raceId", "size"),
                wins=("positionOrder", lambda x: int((x == 1).sum())),
                podiums=("positionOrder", lambda x: int((x <= 3).sum())),
                points=("points", "sum"),
                first=("year", "min"),
                last=("year", "max"),
            )
            .reset_index()
            .sort_values(["points", "races"], ascending=False)
        )
        status = res.loc[res["dnf"], "status"].value_counts().head(8)
        return clean(
            {
                "constructor": info,
                "seasons": records(season),
                "drivers": records(drv.head(40)),
                "dnf_causes": [{"status": k, "count": int(v)} for k, v in status.items()],
            }
        )

    def driver_standings_for(self, year: int) -> list[dict]:
        st = self.final_driver_st[self.final_driver_st["year"] == year]
        teams = self._team_by_season("driverId")
        teams = teams[teams["year"] == year][["driverId", "constructorId", "constructor_name"]]
        out = (
            st.merge(self.drivers[["driverId", "name", "code", "nationality"]], on="driverId")
            .merge(teams, on="driverId", how="left")
            .sort_values("position")
        )
        pod = (
            self.res[self.res["year"] == year]
            .groupby("driverId")["positionOrder"]
            .apply(lambda x: int((x <= 3).sum()))
            .rename("podiums")
        )
        out = out.merge(pod, on="driverId", how="left")
        return records(
            out[
                [
                    "position",
                    "driverId",
                    "name",
                    "code",
                    "nationality",
                    "constructorId",
                    "constructor_name",
                    "points",
                    "wins",
                    "podiums",
                ]
            ]
        )

    def constructor_standings_for(self, year: int) -> list[dict]:
        st = self.final_cons_st[self.final_cons_st["year"] == year]
        out = st.merge(self.constructors[["constructorId", "name", "nationality"]], on="constructorId").sort_values(
            "position"
        )
        pod = (
            self.res[self.res["year"] == year]
            .groupby("constructorId")["positionOrder"]
            .apply(lambda x: int((x <= 3).sum()))
            .rename("podiums")
        )
        out = out.merge(pod, on="constructorId", how="left")
        return records(out[["position", "constructorId", "name", "nationality", "points", "wins", "podiums"]])

    def season_calendar(self, year: int) -> list[dict]:
        r = self.races[self.races["year"] == year].sort_values("round")
        win = self.res[(self.res["year"] == year) & (self.res["positionOrder"] == 1)][
            ["raceId", "driverId", "driver_name", "constructor_name"]
        ]
        pole = (
            self.res[(self.res["year"] == year) & (self.res["grid"] == 1)][["raceId", "driver_name"]]
            .rename(columns={"driver_name": "pole"})
        )
        out = r.merge(win, on="raceId", how="left").merge(pole, on="raceId", how="left")
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        out["sprint"] = out["sprint_date"].notna() if "sprint_date" in out.columns else False
        return records(
            out[
                [
                    "raceId",
                    "round",
                    "race_name",
                    "date",
                    "circuit_name",
                    "location",
                    "country",
                    "lat",
                    "lng",
                    "driverId",
                    "driver_name",
                    "constructor_name",
                    "pole",
                    "sprint",
                ]
            ]
        )

    def meta(self) -> dict:
        ds = self._driver_summary
        return {
            "seasons": self.seasons,
            "latest_season": self.latest_season,
            "driver_nationalities": sorted(ds["nationality"].dropna().unique().tolist()),
            "constructor_nationalities": sorted(self._cons_summary["nationality"].dropna().unique().tolist()),
            "decades": sorted({(y // 10) * 10 for y in self.seasons}),
            "counts": {
                "drivers": int(len(ds)),
                "constructors": int(len(self._cons_summary)),
                "races": int(self.res["raceId"].nunique()),
                "circuits": int(self.races["circuitId"].nunique()),
            },
        }

    def grid_for_season(self, year: int) -> dict:
        """Drivers and constructors who raced in a season (for the profile pickers)."""
        res = self.res[self.res["year"] == year]
        drv = (
            res.groupby(["driverId", "driverRef", "driver_name", "code"])
            .size()
            .reset_index()
            .merge(
                self._team_by_season("driverId").query("year == @year")[["driverId", "constructor_name"]],
                on="driverId",
            )
        )
        cons = res.groupby(["constructorId", "constructorRef", "constructor_name"]).size().reset_index()
        return {
            "drivers": [
                {
                    "ref": r.driverRef,
                    "id": int(r.driverId),
                    "name": r.driver_name,
                    "code": r.code,
                    "team": r.constructor_name,
                }
                for r in drv.itertuples()
            ],
            "constructors": [
                {"ref": r.constructorRef, "id": int(r.constructorId), "name": r.constructor_name}
                for r in cons.itertuples()
            ],
        }

    def driver_by_ref(self, ref: str):
        m = self._driver_summary[self._driver_summary["driverRef"] == ref]
        return None if m.empty else records(m)[0]

    def constructor_by_ref(self, ref: str):
        m = self._cons_summary[self._cons_summary["constructorRef"] == ref]
        return None if m.empty else records(m)[0]


_DATA_CACHE_TTL = 3600  # 1 hour cache TTL
_DATA_CACHE_FILE = Path(tempfile.gettempdir()) / "pitwall_f1_cache_v5.joblib"
_DATA_LOCK = threading.Lock()
_DATA_INSTANCE: F1Data | None = None
_DATA_TIMESTAMP: float = 0.0


def get_data(force_reload: bool = False) -> F1Data:
    """Returns the in-memory F1Data instance, backed by /tmp cache and Supabase Cloud."""
    global _DATA_INSTANCE, _DATA_TIMESTAMP
    now = time.time()
    with _DATA_LOCK:
        if not force_reload and _DATA_INSTANCE is not None and (now - _DATA_TIMESTAMP) < _DATA_CACHE_TTL:
            return _DATA_INSTANCE

        if not force_reload and _DATA_CACHE_FILE.exists():
            try:
                mtime = _DATA_CACHE_FILE.stat().st_mtime
                if (now - mtime) < _DATA_CACHE_TTL:
                    cached_obj = joblib.load(_DATA_CACHE_FILE)
                    if isinstance(cached_obj, F1Data):
                        _DATA_INSTANCE = cached_obj
                        _DATA_TIMESTAMP = mtime
                        logger.info("Loaded F1Data from /tmp cache in <100ms")
                        return _DATA_INSTANCE
            except Exception as e:
                logger.warning(f"Could not load F1Data from disk cache: {e}")

        logger.info("Loading fresh F1Data from Supabase Cloud Database...")
        instance = F1Data()
        _DATA_INSTANCE = instance
        _DATA_TIMESTAMP = now
        try:
            joblib.dump(instance, _DATA_CACHE_FILE, compress=1)
        except Exception as e:
            logger.debug(f"Could not persist F1Data to disk cache: {e}")
        return _DATA_INSTANCE


def reload_data() -> F1Data:
    """Forces an immediate fresh download from Supabase and updates in-memory and disk caches."""
    try:
        if _DATA_CACHE_FILE.exists():
            _DATA_CACHE_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return get_data(force_reload=True)

