"""Loads F1 dataset directly from Supabase Cloud PostgreSQL and keeps precomputed tables in memory.

100% powered by Supabase Cloud Database. No local CSV files or SQLite instances.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any

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
        from concurrent.futures import ThreadPoolExecutor
        from . import db

        client = db.get_supabase_client()

        # Batch 1: Small reference tables fetched concurrently
        with ThreadPoolExecutor(max_workers=6) as pool:
            f_circuits = pool.submit(lambda: client.table("circuits").select("*").limit(1000).execute().data)
            f_constructors = pool.submit(lambda: client.table("constructors").select("*").limit(1000).execute().data)
            f_drivers = pool.submit(lambda: client.table("drivers").select("*").limit(1000).execute().data)
            f_races = pool.submit(
                lambda: client.table("races").select("*").range(0, 999).execute().data
                + client.table("races").select("*").range(1000, 1999).execute().data
            )
            f_status = pool.submit(lambda: client.table("race_statuses").select("*").limit(1000).execute().data)
            f_sprint = pool.submit(lambda: client.table("sprint_results").select("*").limit(1000).execute().data)

        self.circuits = pd.DataFrame(f_circuits.result()).rename(
            columns={"circuit_id": "circuitId", "circuit_ref": "circuitRef"}
        )
        self.constructors = pd.DataFrame(f_constructors.result()).rename(
            columns={"constructor_id": "constructorId", "constructor_ref": "constructorRef"}
        )
        self.drivers = pd.DataFrame(f_drivers.result()).rename(
            columns={"driver_id": "driverId", "driver_ref": "driverRef", "driver_number": "number"}
        )
        self.races = pd.DataFrame(f_races.result()).rename(
            columns={"race_id": "raceId", "circuit_id": "circuitId", "race_date": "date", "race_time": "time"}
        )
        self.status = pd.DataFrame(f_status.result()).rename(
            columns={"status_id": "statusId", "status_name": "status"}
        )
        self.sprint_results = pd.DataFrame(f_sprint.result()).rename(
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

        # Identify season finale race IDs for standings
        last_rounds = self.races.groupby("year")["round"].idxmax()
        final_race_ids = self.races.loc[last_rounds, "raceId"].tolist()

        # Batch 2: Results and Final Standings
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_results = pool.submit(db.fetch_all_rows_parallel, "race_results", "*", 26759)
            f_standings = pool.submit(db.fetch_final_standings, final_race_ids)

        self.results = pd.DataFrame(f_results.result()).rename(
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

        ds_data, cs_data = f_standings.result()
        self.driver_standings = pd.DataFrame(ds_data).rename(
            columns={
                "driver_standings_id": "driverStandingsId",
                "race_id": "raceId",
                "driver_id": "driverId",
                "position_text": "positionText",
            }
        )
        self.constructor_standings = pd.DataFrame(cs_data).rename(
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


@lru_cache(maxsize=1)
def get_data() -> F1Data:
    return F1Data()
