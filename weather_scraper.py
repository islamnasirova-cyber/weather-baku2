"""
Почасовой прогноз погоды для Баку -> weather_baku.csv

Источник:
  - если задана переменная окружения ACCUWEATHER_API_KEY -> официальный API AccuWeather
  - иначе -> Open-Meteo (бесплатно, без ключа)

Запуск:  python weather_scraper.py
Внешние библиотеки не нужны.
"""

import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

CSV_FILE = Path(__file__).with_name("weather_baku.csv")
BAKU_TZ = timezone(timedelta(hours=4))  # Азербайджан: UTC+4, без перехода на летнее время

# 27103 - код Баку, тот же, что в ссылке на accuweather.com
ACCU_LOCATION_KEY = "27103"
BAKU_LAT, BAKU_LON = 40.4093, 49.8671

COLUMNS = [
    "collected_at",
    "source",
    "forecast_time",
    "temperature_c",
    "feels_like_c",
    "humidity_pct",
    "precip_prob_pct",
    "wind_kmh",
    "description",
]


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "weather-baku-script"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_accuweather(api_key):
    """Официальный API AccuWeather: прогноз на 12 часов."""
    params = urllib.parse.urlencode(
        {"apikey": api_key, "language": "ru-ru", "details": "true", "metric": "true"}
    )
    url = (
        "https://dataservice.accuweather.com/forecasts/v1/hourly/12hour/"
        f"{ACCU_LOCATION_KEY}?{params}"
    )
    data = get_json(url)
    rows = []
    for h in data:
        rows.append(
            {
                "forecast_time": h.get("DateTime", ""),
                "temperature_c": (h.get("Temperature") or {}).get("Value", ""),
                "feels_like_c": (h.get("RealFeelTemperature") or {}).get("Value", ""),
                "humidity_pct": h.get("RelativeHumidity", ""),
                "precip_prob_pct": h.get("PrecipitationProbability", ""),
                "wind_kmh": ((h.get("Wind") or {}).get("Speed") or {}).get("Value", ""),
                "description": h.get("IconPhrase", ""),
            }
        )
    return "AccuWeather", rows


# Расшифровка кодов погоды Open-Meteo
WMO = {
    0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность", 3: "Пасмурно",
    45: "Туман", 48: "Изморозь", 51: "Лёгкая морось", 53: "Морось", 55: "Сильная морось",
    61: "Небольшой дождь", 63: "Дождь", 65: "Сильный дождь",
    71: "Небольшой снег", 73: "Снег", 75: "Сильный снег",
    80: "Ливень", 81: "Сильный ливень", 82: "Очень сильный ливень",
    95: "Гроза", 96: "Гроза с градом", 99: "Сильная гроза с градом",
}


def fetch_open_meteo():
    """Open-Meteo: берём ближайшие 12 часов начиная с текущего."""
    params = urllib.parse.urlencode(
        {
            "latitude": BAKU_LAT,
            "longitude": BAKU_LON,
            "hourly": "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "precipitation_probability,wind_speed_10m,weather_code",
            "timezone": "Asia/Baku",
            "forecast_days": 2,
        }
    )
    data = get_json(f"https://api.open-meteo.com/v1/forecast?{params}")
    h = data["hourly"]

    now_hour = datetime.now(BAKU_TZ).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    rows = []
    for i, t in enumerate(h["time"]):
        if datetime.fromisoformat(t) < now_hour:
            continue
        rows.append(
            {
                "forecast_time": t,
                "temperature_c": h["temperature_2m"][i],
                "feels_like_c": h["apparent_temperature"][i],
                "humidity_pct": h["relative_humidity_2m"][i],
                "precip_prob_pct": h["precipitation_probability"][i],
                "wind_kmh": h["wind_speed_10m"][i],
                "description": WMO.get(h["weather_code"][i], str(h["weather_code"][i])),
            }
        )
        if len(rows) == 12:
            break
    return "Open-Meteo", rows


def save_to_csv(source, rows):
    collected_at = datetime.now(BAKU_TZ).strftime("%Y-%m-%d %H:%M:%S")
    is_new = not CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        for r in rows:
            writer.writerow({"collected_at": collected_at, "source": source, **r})


def main():
    api_key = os.environ.get("ACCUWEATHER_API_KEY", "").strip()
    source, rows = None, []

    if api_key:
        try:
            source, rows = fetch_accuweather(api_key)
        except Exception as e:
            print(f"[!] AccuWeather API не сработал ({e}), пробую Open-Meteo")

    if not rows:
        source, rows = fetch_open_meteo()

    save_to_csv(source, rows)
    print(f"[ok] Источник: {source}. Сохранено строк: {len(rows)} -> {CSV_FILE}")


if __name__ == "__main__":
    main()
