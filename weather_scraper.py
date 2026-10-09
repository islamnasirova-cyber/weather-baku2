"""
Сбор почасового прогноза погоды (Баку) с AccuWeather.
Запускается автоматически в 13:00, 16:00 и 19:00 и дописывает данные в CSV.

Установка (один раз):
    pip install playwright schedule
    playwright install chromium

Запуск:
    python weather_scraper.py          # ждёт 13:00 / 16:00 / 19:00 и работает постоянно
    python weather_scraper.py --now    # собрать данные прямо сейчас (для проверки)
"""

import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = "https://www.accuweather.com/ru/az/baku/27103/hourly-weather-forecast/27103"
RUN_TIMES = ["13:00", "16:00", "19:00"]  # время берётся из часов компьютера

BASE_DIR = Path(__file__).parent
CSV_FILE = BASE_DIR / "weather_baku.csv"
DEBUG_FILE = BASE_DIR / "debug_page.txt"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def accept_cookies(page):
    """Закрываем окно согласия с cookie, если оно появилось."""
    for selector in [
        "button.fc-cta-consent",
        "button:has-text('Принять')",
        "button:has-text('Согласен')",
        "button:has-text('Accept')",
    ]:
        try:
            page.click(selector, timeout=3000)
            return
        except Exception:
            continue


def fetch_hourly():
    """Открывает страницу и возвращает список строк: по одной на каждый час."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="ru-RU", user_agent=USER_AGENT)
        page = context.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            accept_cookies(page)

            try:
                page.wait_for_selector(".hourly-card-nfl", timeout=20_000)
            except PWTimeout:
                # Если карточек нет — сохраняем текст страницы для отладки
                DEBUG_FILE.write_text(page.inner_text("body"), encoding="utf-8")
                print(f"[!] Карточки не найдены. Текст страницы сохранён в {DEBUG_FILE}")
                return []

            rows = []
            for card in page.query_selector_all(".hourly-card-nfl"):
                lines = [l.strip() for l in card.inner_text().split("\n") if l.strip()]
                if not lines:
                    continue
                full_text = " | ".join(lines)
                temp_match = re.search(r"-?\d+\s*°", full_text)
                rows.append(
                    {
                        "hour": lines[0],
                        "temperature": temp_match.group(0) if temp_match else "",
                        "details": full_text,
                    }
                )
            return rows
        finally:
            browser.close()


def save_to_csv(rows):
    """Дописывает данные в CSV (создаёт файл с заголовком, если его нет)."""
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_new = not CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["collected_at", "hour", "temperature", "details"])
        for r in rows:
            writer.writerow([collected_at, r["hour"], r["temperature"], r["details"]])


def job():
    print(f"[{datetime.now():%H:%M:%S}] Собираю данные...")
    try:
        rows = fetch_hourly()
    except Exception as e:
        print(f"[!] Ошибка: {e}")
        return
    if rows:
        save_to_csv(rows)
        print(f"[ok] Сохранено строк: {len(rows)} -> {CSV_FILE}")


def main():
    if "--now" in sys.argv:
        job()
        return

    for t in RUN_TIMES:
        schedule.every().day.at(t).do(job)
    print(f"Скрипт запущен. Сбор данных в: {', '.join(RUN_TIMES)}. Остановить: Ctrl+C")

    while True:
        schedule.run_pending()
        time.sleep(20)


if __name__ == "__main__":
    main()
