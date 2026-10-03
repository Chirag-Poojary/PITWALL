"""Migration Script: Ingests all PITWALL CSVs from backend/data/ into Supabase PostgreSQL.

Usage:
    python scripts/migrate_csv_to_supabase.py
    python scripts/migrate_csv_to_supabase.py --skip-lap-times
    python scripts/migrate_csv_to_supabase.py --table drivers
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "backend" / "data"

COLUMN_MAPS: dict[str, dict[str, str]] = {
    "race_statuses": {
        "statusId": "status_id",
        "status": "status_name",
    },
    "seasons": {
        "year": "year",
        "url": "url",
    },
    "circuits": {
        "circuitId": "circuit_id",
        "circuitRef": "circuit_ref",
        "name": "name",
        "location": "location",
        "country": "country",
        "lat": "lat",
        "lng": "lng",
        "alt": "alt",
        "url": "url",
    },
    "constructors": {
        "constructorId": "constructor_id",
        "constructorRef": "constructor_ref",
        "name": "name",
        "nationality": "nationality",
        "url": "url",
    },
    "drivers": {
        "driverId": "driver_id",
        "driverRef": "driver_ref",
        "number": "driver_number",
        "code": "code",
        "forename": "forename",
        "surname": "surname",
        "dob": "dob",
        "nationality": "nationality",
        "url": "url",
    },
    "races": {
        "raceId": "race_id",
        "year": "year",
        "round": "round",
        "circuitId": "circuit_id",
        "name": "name",
        "date": "race_date",
        "time": "race_time",
        "url": "url",
        "fp1_date": "fp1_date",
        "fp1_time": "fp1_time",
        "fp2_date": "fp2_date",
        "fp2_time": "fp2_time",
        "fp3_date": "fp3_date",
        "fp3_time": "fp3_time",
        "quali_date": "quali_date",
        "quali_time": "quali_time",
        "sprint_date": "sprint_date",
        "sprint_time": "sprint_time",
    },
    "race_results": {
        "resultId": "result_id",
        "raceId": "race_id",
        "driverId": "driver_id",
        "constructorId": "constructor_id",
        "number": "driver_number",
        "grid": "grid",
        "position": "position",
        "positionText": "position_text",
        "positionOrder": "position_order",
        "points": "points",
        "laps": "laps",
        "time": "race_time",
        "milliseconds": "milliseconds",
        "fastestLap": "fastest_lap",
        "rank": "fastest_lap_rank",
        "fastestLapTime": "fastest_lap_time",
        "fastestLapSpeed": "fastest_lap_speed",
        "statusId": "status_id",
    },
    "qualifying_results": {
        "qualifyId": "qualify_id",
        "raceId": "race_id",
        "driverId": "driver_id",
        "constructorId": "constructor_id",
        "number": "driver_number",
        "position": "position",
        "q1": "q1",
        "q2": "q2",
        "q3": "q3",
    },
    "sprint_results": {
        "resultId": "sprint_result_id",
        "raceId": "race_id",
        "driverId": "driver_id",
        "constructorId": "constructor_id",
        "number": "driver_number",
        "grid": "grid",
        "position": "position",
        "positionText": "position_text",
        "positionOrder": "position_order",
        "points": "points",
        "laps": "laps",
        "time": "race_time",
        "milliseconds": "milliseconds",
        "fastestLap": "fastest_lap",
        "fastestLapTime": "fastest_lap_time",
        "statusId": "status_id",
    },
    "pit_stops": {
        "raceId": "race_id",
        "driverId": "driver_id",
        "stop": "stop_number",
        "lap": "lap",
        "time": "stop_time",
        "duration": "stop_duration",
        "milliseconds": "milliseconds",
    },
    "driver_standings": {
        "driverStandingsId": "driver_standings_id",
        "raceId": "race_id",
        "driverId": "driver_id",
        "points": "points",
        "position": "position",
        "positionText": "position_text",
        "wins": "wins",
    },
    "constructor_standings": {
        "constructorStandingsId": "constructor_standings_id",
        "raceId": "race_id",
        "constructorId": "constructor_id",
        "points": "points",
        "position": "position",
        "positionText": "position_text",
        "wins": "wins",
    },
    "constructor_results": {
        "constructorResultsId": "constructor_results_id",
        "raceId": "race_id",
        "constructorId": "constructor_id",
        "points": "points",
        "status": "status",
    },
    "lap_times": {
        "raceId": "race_id",
        "driverId": "driver_id",
        "lap": "lap",
        "position": "position",
        "time": "lap_time_str",
        "milliseconds": "milliseconds",
    },
}

TABLE_ORDER: list[tuple[str, str]] = [
    ("status.csv", "race_statuses"),
    ("seasons.csv", "seasons"),
    ("circuits.csv", "circuits"),
    ("constructors.csv", "constructors"),
    ("drivers.csv", "drivers"),
    ("races.csv", "races"),
    ("results.csv", "race_results"),
    ("qualifying.csv", "qualifying_results"),
    ("sprint_results.csv", "sprint_results"),
    ("pit_stops.csv", "pit_stops"),
    ("driver_standings.csv", "driver_standings"),
    ("constructor_standings.csv", "constructor_standings"),
    ("constructor_results.csv", "constructor_results"),
    ("lap_times.csv", "lap_times"),
]


def get_client():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("[ERROR] SUPABASE_URL and SUPABASE_KEY must be set in your .env file.")
        sys.exit(1)
    return create_client(url, key)


def clean_dataframe(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Rename columns, convert NaN/None types, and clean formatting."""
    mapping = COLUMN_MAPS.get(table_name, {})
    if mapping:
        df = df.rename(columns=mapping)
        # Keep only mapped columns that belong to target schema
        df = df[[c for c in mapping.values() if c in df.columns]]

    # Replace all nulls / NaNs with None
    df = df.replace({np.nan: None})
    return df


FLOAT_COLUMNS = {"lat", "lng", "points", "fastest_lap_speed"}

INTEGER_COLUMNS = {
    "status_id", "year", "circuit_id", "alt", "constructor_id", "driver_id",
    "driver_number", "race_id", "round", "result_id", "grid", "position",
    "position_order", "laps", "milliseconds", "fastest_lap", "fastest_lap_rank",
    "qualify_id", "sprint_result_id", "stop_number", "driver_standings_id",
    "constructor_standings_id", "constructor_results_id", "wins", "lap"
}


def upload_table(client, table_name: str, df: pd.DataFrame, batch_size: int = 1500):
    total = len(df)
    records = df.to_dict(orient="records")

    # Clean records: convert numpy scalar types to native python, ensuring strict int/float fidelity
    clean_records = []
    for r in records:
        cleaned = {}
        for k, v in r.items():
            if pd.isna(v) or v is None:
                cleaned[k] = None
            elif k in INTEGER_COLUMNS:
                try:
                    cleaned[k] = int(float(v))
                except (ValueError, TypeError):
                    cleaned[k] = None
            elif k in FLOAT_COLUMNS:
                try:
                    cleaned[k] = float(v)
                except (ValueError, TypeError):
                    cleaned[k] = None
            elif isinstance(v, (np.integer, int)):
                cleaned[k] = int(v)
            elif isinstance(v, (np.floating, float)):
                cleaned[k] = int(v) if float(v).is_integer() else float(v)
            else:
                cleaned[k] = str(v)
        clean_records.append(cleaned)

    print(f"Uploading {total:,} rows to '{table_name}' in batches of {batch_size}...")
    start_t = time.time()
    for i in range(0, total, batch_size):
        batch = clean_records[i : i + batch_size]
        try:
            client.table(table_name).upsert(batch).execute()
        except Exception as e:
            print(f"\n[ERROR] Failed to upsert batch {i}-{i+len(batch)} into '{table_name}': {e}")
            raise e
        done = min(i + batch_size, total)
        percent = (done / total) * 100
        print(f"\r  [{table_name}] Progress: {done:,}/{total:,} rows ({percent:.1f}%)", end="", flush=True)

    elapsed = time.time() - start_t
    print(f"\r  [{table_name}] Complete: {total:,} rows uploaded in {elapsed:.1f}s.")


def main():
    parser = argparse.ArgumentParser(description="Migrate F1 CSVs to Supabase")
    parser.add_argument("--skip-lap-times", action="store_true", help="Skip lap_times.csv (589k rows)")
    parser.add_argument("--table", type=str, help="Migrate a specific table only")
    parser.add_argument("--from-table", type=str, help="Resume migration starting from this table onwards")
    parser.add_argument("--batch-size", type=int, default=1500, help="Batch size for upsert (default: 1500)")
    args = parser.parse_args()

    client = get_client()

    # Pre-check schema readiness
    try:
        client.table("race_statuses").select("status_id").limit(1).execute()
    except Exception as e:
        print("\n" + "=" * 76)
        print("[ERROR] Tables not found in Supabase project!")
        print("Please execute the schema file in your Supabase SQL Editor first:")
        print("  1. Open: https://supabase.com/dashboard/project/_/sql")
        print("  2. Open and copy: d:\\chirag\\FOne\\supabase_schema.sql")
        print("  3. Click 'Run' to create all tables, indexes, and views.")
        print("=" * 76 + "\n")
        sys.exit(1)

    tables_to_migrate = TABLE_ORDER
    if args.table:
        tables_to_migrate = [(f"{args.table}.csv", args.table) for _, t in TABLE_ORDER if t == args.table]
        if not tables_to_migrate:
            print(f"[ERROR] Table '{args.table}' not found in migration mapping.")
            sys.exit(1)
    elif args.from_table:
        start_idx = next((i for i, (_, t) in enumerate(TABLE_ORDER) if t == args.from_table), None)
        if start_idx is None:
            print(f"[ERROR] Table '{args.from_table}' not found in migration mapping.")
            sys.exit(1)
        tables_to_migrate = TABLE_ORDER[start_idx:]

    print(f"Starting PITWALL F1 Data Migration to Supabase...")
    for csv_file, table_name in tables_to_migrate:
        if args.skip_lap_times and table_name == "lap_times":
            print(f"\nSkipping '{table_name}' as requested.")
            continue

        file_path = DATA_DIR / csv_file
        if not file_path.exists():
            print(f"\n[WARNING] CSV file {file_path.name} not found. Skipping.")
            continue

        print(f"\nProcessing {csv_file} -> {table_name}...")
        df = pd.read_csv(file_path, na_values=["\\N", ""], keep_default_na=True, low_memory=False)
        df = clean_dataframe(df, table_name)
        upload_table(client, table_name, df, batch_size=args.batch_size)

    print("\n" + "=" * 76)
    print("MIGRATION FINISHED SUCCESSFULLY!")
    print("All F1 tables have been populated into Supabase.")
    print("=" * 76)


if __name__ == "__main__":
    main()
