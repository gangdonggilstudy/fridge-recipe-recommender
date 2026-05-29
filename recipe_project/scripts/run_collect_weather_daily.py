import argparse
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from db.repository import (
    find_review_date_range,
    upsert_weather_daily,
)


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="날씨 수집 시작일. 예: 2024-01-01"
    )

    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="날씨 수집 종료일. 예: 2024-12-31"
    )

    parser.add_argument(
        "--latitude",
        type=float,
        default=37.5665,
        help="위도. 기본값 서울"
    )

    parser.add_argument(
        "--longitude",
        type=float,
        default=126.9780,
        help="경도. 기본값 서울"
    )

    return parser.parse_args()


def to_date(value) -> date:
    if isinstance(value, date):
        return value

    return datetime.strptime(str(value), "%Y-%m-%d").date()


def fetch_open_meteo_hourly(
        start_date: date,
        end_date: date,
        latitude: float,
        longitude: float
) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
        ],
        "timezone": "Asia/Seoul",
    }

    response = requests.get(
        OPEN_METEO_ARCHIVE_URL,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    return response.json()


def aggregate_hourly_to_daily(data: dict) -> list[dict]:
    hourly = data.get("hourly", {})

    if not hourly:
        return []

    df = pd.DataFrame({
        "time": hourly.get("time", []),
        "temperature": hourly.get("temperature_2m", []),
        "humidity": hourly.get("relative_humidity_2m", []),
        "precipitation": hourly.get("precipitation", []),
    })

    if df.empty:
        return []

    df["time"] = pd.to_datetime(df["time"])
    df["weather_date"] = df["time"].dt.date

    daily = (
        df.groupby("weather_date")
          .agg(
              avg_temp=("temperature", "mean"),
              min_temp=("temperature", "min"),
              max_temp=("temperature", "max"),
              avg_humidity=("humidity", "mean"),
              rainfall=("precipitation", "sum"),
          )
          .reset_index()
    )

    rows = []

    for _, row in daily.iterrows():
        rainfall = float(row["rainfall"] or 0)

        rows.append({
            "weather_date": row["weather_date"].isoformat(),
            "avg_temp": round(float(row["avg_temp"]), 2) if pd.notna(row["avg_temp"]) else None,
            "min_temp": round(float(row["min_temp"]), 2) if pd.notna(row["min_temp"]) else None,
            "max_temp": round(float(row["max_temp"]), 2) if pd.notna(row["max_temp"]) else None,
            "avg_humidity": round(float(row["avg_humidity"]), 2) if pd.notna(row["avg_humidity"]) else None,
            "rainfall": round(rainfall, 2),
            "rain_yn": "Y" if rainfall > 0 else "N",
            "source": "OPEN_METEO",
        })

    return rows


def date_chunks(start_date: date, end_date: date, chunk_days: int = 90):
    current = start_date

    while current <= end_date:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end_date)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def main():
    args = parse_args()

    if args.start_date and args.end_date:
        start_date = to_date(args.start_date)
        end_date = to_date(args.end_date)
    else:
        date_range = find_review_date_range()

        if not date_range["min_date"] or not date_range["max_date"]:
            raise ValueError("raw_recipe_review에 review_date가 없습니다.")

        start_date = to_date(date_range["min_date"])
        end_date = to_date(date_range["max_date"])

    print(f"weather range: {start_date} ~ {end_date}")
    print(f"location: lat={args.latitude}, lon={args.longitude}")

    saved_count = 0

    for chunk_start, chunk_end in date_chunks(start_date, end_date, chunk_days=90):
        print(f"fetch weather: {chunk_start} ~ {chunk_end}")

        data = fetch_open_meteo_hourly(
            start_date=chunk_start,
            end_date=chunk_end,
            latitude=args.latitude,
            longitude=args.longitude
        )

        rows = aggregate_hourly_to_daily(data)

        for row in rows:
            upsert_weather_daily(row)
            saved_count += 1

        print(f"saved daily weather rows={len(rows)}")

    print(f"done. total_saved_count={saved_count}")


if __name__ == "__main__":
    main()