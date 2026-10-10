"""
Текущая погода в Баку (на момент запуска) -> weather_baku.csv

Источник:
  - если задана переменная окружения ACCUWEATHER_API_KEY -> AccuWeather API (текущие условия)
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
OLD_CSV_FILE = Path(__file__).with_name("weather_baku_forecast_old.csv")
BAKU_TZ = timezone(timedelta(hours=4))  # Азербайджан: UTC+4, без перехода на летнее время

ACCU_LOCATION_KEY = "27103"  # код Баку, тот же, что в ссылке на accuweather.com
BAKU_LAT, BAKU_LON = 40.4093, 49.8671

COLUMNS = [
    "collected_at",
    "source",
    "observation_time",
    "temperature_c",
    "feels_like_c",
    "humidity_pct",
    "precipitation_mm",
    "wind_kmh",
    "description",
]

# Расшифровка кодов погоды Open-Meteo
WMO = {
    0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность", 3: "Пасмурно",
    45: "Туман", 48: "Изморозь", 51: "Лёгкая морось", 53: "Морось", 55: "Сильная морось",
    61: "Небольшой дождь", 63: "Дождь", 65: "Сильный дождь",
    71: "Небольшой снег", 73: "Снег", 75: "Сильный снег",
    80: "Слабый ливень", 81: "Ливень", 82: "Сильный ливень",
    95: "Гроза", 96: "Гроза с градом", 99: "Сильная гроза с градом",
}


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "weather-baku-script"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_open_meteo():
    """Open-Meteo: текущие условия (блок current), не прогноз."""
    params = urllib.parse.urlencode(
        {
            "latitude": BAKU_LAT,
            "longitude": BAKU_LON,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "precipitation,wind_speed_10m,weather_code",
            "timezone": "Asia/Baku",
        }
    )
    c = get_json(f"https://api.open-meteo.com/v1/forecast?{params}")["current"]
    row = {
        "observation_time": c["time"],
        "temperature_c": c["temperature_2m"],
        "feels_like_c": c["apparent_temperature"],
        "humidity_pct": c["relative_humidity_2m"],
        "precipitation_mm": c["precipitation"],
        "wind_kmh": c["wind_speed_10m"],
        "description": WMO.get(c["weather_code"], str(c["weather_code"])),
    }
    return "Open-Meteo", row


def fetch_accuweather(api_key):
    """AccuWeather API: текущие условия."""
    params = urllib.parse.urlencode({"apikey": api_key, "language": "ru-ru", "details": "true"})
    url = f"https://dataservice.accuweather.com/currentconditions/v1/{ACCU_LOCATION_KEY}?{params}"
    c = get_json(url)[0]
    metric = lambda d: ((d or {}).get("Metric") or {}).get("Value", "")
    row = {
        "observation_time": c.get("LocalObservationDateTime", ""),
        "temperature_c": metric(c.get("Temperature")),
        "feels_like_c": metric(c.get("RealFeelTemperature")),
        "humidity_pct": c.get("RelativeHumidity", ""),
        "precipitation_mm": metric(c.get("PrecipitationSummary", {}).get("PastHour")),
        "wind_kmh": metric((c.get("Wind") or {}).get("Speed")),
        "description": c.get("WeatherText", ""),
    }
    return "AccuWeather", row


def save_to_csv(source, row):
    collected_at = datetime.now(BAKU_TZ).strftime("%Y-%m-%d %H:%M:%S")

    # Если в файле старый формат (прогноз на 12 часов) - откладываем его в сторону
    if CSV_FILE.exists():
        first_line = CSV_FILE.read_text(encoding="utf-8-sig").splitlines()[:1]
        if first_line and first_line[0].strip() != ",".join(COLUMNS):
            CSV_FILE.replace(OLD_CSV_FILE)

    is_new = not CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow({"collected_at": collected_at, "source": source, **row})


def main():
    api_key = os.environ.get("ACCUWEATHER_API_KEY", "").strip()
    result = None

    if api_key:
        try:
            result = fetch_accuweather(api_key)
        except Exception as e:
            print(f"[!] AccuWeather API не сработал ({e}), пробую Open-Meteo")

    if result is None:
        result = fetch_open_meteo()

    source, row = result
    save_to_csv(source, row)
    print(f"[ok] {source}: {row['observation_time']}, {row['temperature_c']} °C, "
          f"{row['description']} -> {CSV_FILE}")


if __name__ == "__main__":
    main()
