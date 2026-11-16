#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kindle dashboard: погода (Open-Meteo) + графики отключений света (Yasno) -> PNG (8-bit grayscale).

Запуск:
    python dashboard.py            # реальные данные
    python dashboard.py --demo     # демо-данные (без интернета), чтобы посмотреть вёрстку
Настройки: config.json
"""

import argparse
import json
import math
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")

BLACK, DARK, MID, LIGHT, WHITE = 0, 70, 140, 215, 255

DEFAULTS = {
    "language": "ru",
    "timezone": "Europe/Kyiv",
    "screen": {"width": 758, "height": 1024, "rotate": 0},
    "weather": {"city": "Kyiv", "display_name": None, "latitude": None, "longitude": None,
                "model": "icon_seamless"},
    "yasno": {"region_id": 25, "dso_id": 902},
    "groups": [
        {"label": "Дом", "group": "7.1"},
        {"label": "Работа", "group": "5.1"},
    ],
    "output": "dist/dashboard.png",
}

# ----------------------------------------------------------------------------
# Тексты
# ----------------------------------------------------------------------------
I18N = {
    "ru": {
        "outages": "Отключения света",
        "today": "Сегодня", "tomorrow": "Завтра",
        "group_abbr": "гр.",
        "on_until": "Свет есть до {t}", "off_until": "Света нет до {t}",
        "none": "Отключений не ожидается", "tmrw_word": "завтра",
        "emergency": "АВАРИЙНЫЕ ОТКЛЮЧЕНИЯ · график может не действовать",
        "stale_prefix": "прежний: ",
        "offline": "YASNO НЕДОСТУПЕН · показан последний сохранённый график",
        "no_data_day": "нет сохранённых данных",
        "waiting": "график ещё не опубликован",
        "no_outages_day": "отключений нет",
        "void": "графики не действуют",
        "group_missing": "группа не найдена в ответе Yasno",
        "feels": "Ощущается", "wind": "Ветер", "ms": "м/с",
        "updated": "Обновлено",
        "no_weather": "Нет данных о погоде",
        "no_outage_data": "Нет данных Yasno",
        "weekdays": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
        "weekdays_full": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
        "months_full": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
                        "сентября", "октября", "ноября", "декабря"],
        "months": ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
        "weather": {"clear": "Ясно", "partly": "Переменная облачность", "cloud": "Облачно",
                    "fog": "Туман", "drizzle": "Морось", "rain": "Дождь",
                    "snow": "Снег", "thunder": "Гроза"},
    },
    "uk": {
        "outages": "Відключення світла",
        "today": "Сьогодні", "tomorrow": "Завтра",
        "group_abbr": "гр.",
        "on_until": "Світло є до {t}", "off_until": "Світла немає до {t}",
        "none": "Відключень не очікується", "tmrw_word": "завтра",
        "emergency": "АВАРІЙНІ ВІДКЛЮЧЕННЯ · графік може не діяти",
        "stale_prefix": "попередній: ",
        "offline": "YASNO НЕДОСТУПНИЙ · показано останній збережений графік",
        "no_data_day": "немає збережених даних",
        "waiting": "графік ще не опубліковано",
        "no_outages_day": "відключень немає",
        "void": "графіки не діють",
        "group_missing": "групу не знайдено у відповіді Yasno",
        "feels": "Відчувається", "wind": "Вітер", "ms": "м/с",
        "updated": "Оновлено",
        "no_weather": "Немає даних про погоду",
        "no_outage_data": "Немає даних Yasno",
        "weekdays": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"],
        "weekdays_full": ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"],
        "months_full": ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня",
                        "вересня", "жовтня", "листопада", "грудня"],
        "months": ["січ", "лют", "бер", "кві", "тра", "чер", "лип", "сер", "вер", "жов", "лис", "гру"],
        "weather": {"clear": "Ясно", "partly": "Мінлива хмарність", "cloud": "Хмарно",
                    "fog": "Туман", "drizzle": "Мряка", "rain": "Дощ",
                    "snow": "Сніг", "thunder": "Гроза"},
    },
    "en": {
        "outages": "Power outages",
        "today": "Today", "tomorrow": "Tomorrow",
        "group_abbr": "grp",
        "on_until": "Power on until {t}", "off_until": "Power off until {t}",
        "none": "No outages expected", "tmrw_word": "tmrw",
        "emergency": "EMERGENCY OUTAGES · schedule may not apply",
        "stale_prefix": "previous: ",
        "offline": "YASNO UNAVAILABLE · showing last saved schedule",
        "no_data_day": "no saved data",
        "waiting": "schedule not published yet",
        "no_outages_day": "no outages",
        "void": "schedules suspended",
        "group_missing": "group not found in Yasno response",
        "feels": "Feels like", "wind": "Wind", "ms": "m/s",
        "updated": "Updated",
        "no_weather": "No weather data",
        "no_outage_data": "No Yasno data",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "weekdays_full": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months_full": ["January", "February", "March", "April", "May", "June", "July", "August",
                        "September", "October", "November", "December"],
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "weather": {"clear": "Clear", "partly": "Partly cloudy", "cloud": "Cloudy",
                    "fog": "Fog", "drizzle": "Drizzle", "rain": "Rain",
                    "snow": "Snow", "thunder": "Thunderstorm"},
    },
}


# ----------------------------------------------------------------------------
# Конфиг
# ----------------------------------------------------------------------------
def load_config(path):
    user = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = json.loads(json.dumps(DEFAULTS))
    for key, val in user.items():
        if isinstance(val, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(val)
        else:
            cfg[key] = val
    return cfg


# ----------------------------------------------------------------------------
# Получение данных
# ----------------------------------------------------------------------------
def http_get_json(url, params=None, retries=3):
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=25,
                             headers={"User-Agent": UA, "Accept": "application/json"})
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(2 * (i + 1))
    raise last


MODEL_LABELS = {
    "icon_seamless": "DWD ICON", "icon_global": "DWD ICON", "icon_eu": "DWD ICON EU",
    "icon_d2": "DWD ICON D2",
}


def fetch_weather(cfg):
    w = cfg["weather"]
    lang = cfg["language"]
    lat, lon, name = w.get("latitude"), w.get("longitude"), w.get("city")
    if lat is None or lon is None:
        g = http_get_json("https://geocoding-api.open-meteo.com/v1/search",
                          {"name": w["city"], "count": 1, "language": lang, "format": "json"})
        res = g.get("results")
        if not res:
            raise RuntimeError(f"Город не найден: {w['city']}")
        lat, lon, name = res[0]["latitude"], res[0]["longitude"], res[0]["name"]
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "wind_speed_unit": "ms",
        "timezone": "auto",
        "forecast_days": 5,
    }
    model = w.get("model")
    label = "Open-Meteo"
    if model:
        try:
            data = http_get_json("https://api.open-meteo.com/v1/forecast", dict(params, models=model))
            label = MODEL_LABELS.get(model, model)
        except Exception as e:  # noqa: BLE001
            print(f"[!] Модель {model} недоступна ({e!r}), беру модель по умолчанию", file=sys.stderr)
            data = http_get_json("https://api.open-meteo.com/v1/forecast", params)
    else:
        data = http_get_json("https://api.open-meteo.com/v1/forecast", params)
    return {"name": w.get("display_name") or name, "label": label,
            "current": data["current"], "daily": data["daily"]}


def fetch_outages(cfg):
    y = cfg["yasno"]
    url = (f"https://app.yasno.ua/api/blackout-service/public/shutdowns/"
           f"regions/{y['region_id']}/dsos/{y['dso_id']}/planned-outages")
    data = http_get_json(url)
    if not isinstance(data, dict):
        raise RuntimeError("Неожиданный формат ответа Yasno")
    return data


def parse_day(day):
    """Слоты в Yasno: минуты от полуночи, start..end = свет ВЫКЛЮЧЕН."""
    if not day:
        return {"known": False, "emergency": False, "stale": False, "date": "", "slots": []}
    status = str(day.get("status", "")).lower()
    slots = []
    for s in day.get("slots") or []:
        kind = str(s.get("type", "Definite")).lower()
        if kind in ("notplanned", "not_planned"):
            continue
        slots.append((int(s["start"]), int(s["end"]),
                      "possible" if kind == "possible" else "definite"))
    slots.sort()
    return {"known": "waiting" not in status,
            "emergency": "emergency" in status,
            "stale": False,
            "date": str(day.get("date") or "")[:10],
            "slots": slots}


def build_outages(raw, groups, state, now):
    """При EmergencyShutdowns Yasno не отдаёт нормальный график: берём последний
    сохранённый график на эту дату (state) и помечаем его как устаревший."""
    res = {}
    fallback = {"today": now.date(), "tomorrow": now.date() + timedelta(days=1)}
    saved_all = state.setdefault("groups", {})
    for g in groups:
        gid = str(g["group"])
        item = raw.get(gid)
        if item is None:
            print(f"[!] Группа {gid} не найдена. Доступные: {', '.join(sorted(raw.keys()))}",
                  file=sys.stderr)
            res[gid] = None
            continue
        saved = saved_all.setdefault(gid, {})
        days = {}
        for key in ("today", "tomorrow"):
            day = parse_day(item.get(key))
            date = day["date"] or fallback[key].isoformat()
            day["date"] = date
            if day["emergency"]:
                prev = saved.get(date)
                if prev is not None:
                    day["slots"] = [(int(a), int(b), k) for a, b, k in prev]
                    day["stale"] = True
            elif day["known"]:
                saved[date] = [[a, b, k] for a, b, k in day["slots"]]
            days[key] = day
        # чистим старые даты (оставляем вчера и новее)
        limit = (now.date() - timedelta(days=1)).isoformat()
        for d_ in [d_ for d_ in saved if d_ < limit]:
            del saved[d_]
        res[gid] = days
    return res


def outages_from_state(groups, state, now):
    """Yasno недоступен: собираем графики из последнего сохранённого состояния.
    Возвращает None, если для выбранных групп ничего не сохранено."""
    dates = {"today": now.date().isoformat(),
             "tomorrow": (now.date() + timedelta(days=1)).isoformat()}
    saved_all = state.get("groups", {})
    res, found = {}, False
    for g in groups:
        gid = str(g["group"])
        saved = saved_all.get(gid, {})
        days = {}
        for key, date in dates.items():
            prev = saved.get(date)
            found = found or prev is not None
            days[key] = {"known": prev is not None, "emergency": False, "stale": True,
                         "offline": True, "date": date,
                         "slots": [(int(a), int(b), k) for a, b, k in (prev or [])]}
        res[gid] = days
    return res if found else None


def load_state(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


# ----------------------------------------------------------------------------
# Логика расписания
# ----------------------------------------------------------------------------
def merge(intervals):
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def hm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def fmt_clock(m, T):
    if m == 1440:
        return "24:00"
    if m > 1440:
        return f"{hm(m - 1440)} {T['tmrw_word']}"
    return hm(m)


def power_status(today, tomorrow, now_min):
    iv = [(s, e) for s, e, _ in today["slots"]]
    iv += [(s + 1440, e + 1440) for s, e, _ in tomorrow["slots"]]
    merged = merge(iv)
    for s, e in merged:
        if s <= now_min < e:
            return "off", e
    for s, e in merged:
        if s > now_min:
            return "on", s
    return "none", None


def intervals_text(day, T):
    if not day["known"]:
        return T["no_data_day"] if day.get("offline") else T["waiting"]
    iv = merge([(s, e) for s, e, _ in day["slots"]])
    if not iv:
        return T["void"] if day["emergency"] else T["no_outages_day"]
    text = ", ".join(f"{hm(s)}–{hm(e)}" for s, e in iv)
    return (T["stale_prefix"] + text) if day.get("stale") else text


# ----------------------------------------------------------------------------
# Шрифты и текст
# ----------------------------------------------------------------------------
FONTS_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf", "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
FONTS_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
_font_cache = {}


def font(size, bold=False):
    size = max(8, int(round(size)))
    key = (size, bold)
    if key not in _font_cache:
        f = None
        for path in (FONTS_BOLD if bold else FONTS_REGULAR):
            try:
                f = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
        if f is None:
            print("[!] Не найден шрифт с кириллицей (DejaVu Sans / Arial)", file=sys.stderr)
            f = ImageFont.load_default(size)
        _font_cache[key] = f
    return _font_cache[key]


def fit_font(d, text, max_w, size, bold=False, min_size=12):
    size = int(round(size))
    min_size = int(round(min_size))
    while size > min_size and d.textlength(text, font=font(size, bold)) > max_w:
        size -= 1
    return font(size, bold)


def ellipsize(d, text, f, max_w):
    if d.textlength(text, font=f) <= max_w:
        return text
    while len(text) > 1 and d.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text + "…"


def fmt_t(v):
    if v is None:
        return "—"
    n = int(round(v))
    if n == 0:
        return "0°"
    return f"{'+' if n > 0 else '−'}{abs(n)}°"


def date_str(now, T):
    return f"{T['weekdays'][now.weekday()]}, {now.day} {T['months'][now.month - 1]}"


# ----------------------------------------------------------------------------
# Иконки погоды
# ----------------------------------------------------------------------------
def wmo_category(code):
    if code is None:      # модель может не покрывать последний день прогноза
        return None
    code = int(code)
    if code in (0, 1):
        return "clear"
    if code == 2:
        return "partly"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 57:
        return "drizzle"
    if 61 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if code >= 95:
        return "thunder"
    return "cloud"


def _circle(d, cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def draw_cloud(d, cx, cy, s, fill=LIGHT):
    g = max(2, s * 0.05)
    parts = [
        ("c", cx - 0.20 * s, cy + 0.05 * s, 0.22 * s),
        ("c", cx + 0.05 * s, cy - 0.10 * s, 0.30 * s),
        ("c", cx + 0.28 * s, cy + 0.08 * s, 0.20 * s),
        ("r", cx - 0.20 * s, cy + 0.05 * s, cx + 0.28 * s, cy + 0.28 * s),
    ]
    for grow, color in ((g, BLACK), (0, fill)):
        for p in parts:
            if p[0] == "c":
                _circle(d, p[1], p[2], p[3] + grow, color)
            else:
                d.rectangle([p[1], p[2], p[3], p[4] + grow], fill=color)


def draw_sun(d, cx, cy, s):
    r = 0.22 * s
    w = max(2, int(s * 0.06))
    for i in range(8):
        a = math.radians(i * 45)
        d.line([(cx + math.cos(a) * r * 1.45, cy + math.sin(a) * r * 1.45),
                (cx + math.cos(a) * r * 2.05, cy + math.sin(a) * r * 2.05)], fill=BLACK, width=w)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE, outline=BLACK, width=w)


def draw_icon(d, cat, cx, cy, s):
    w = max(2, int(s * 0.06))
    if cat == "clear":
        draw_sun(d, cx, cy, s)
    elif cat == "partly":
        draw_sun(d, cx - 0.16 * s, cy - 0.16 * s, 0.75 * s)
        draw_cloud(d, cx + 0.08 * s, cy + 0.10 * s, 0.85 * s)
    elif cat == "cloud":
        draw_cloud(d, cx - 0.12 * s, cy - 0.12 * s, 0.7 * s, fill=MID)
        draw_cloud(d, cx + 0.05 * s, cy + 0.08 * s, 0.9 * s)
    elif cat == "fog":
        for i, dy in enumerate((-0.22, -0.07, 0.08, 0.23)):
            shift = 0.06 * s if i % 2 else -0.06 * s
            d.line([(cx - 0.36 * s + shift, cy + dy * s), (cx + 0.36 * s + shift, cy + dy * s)],
                   fill=BLACK, width=w + 1)
    elif cat in ("rain", "drizzle"):
        draw_cloud(d, cx, cy - 0.12 * s, s)
        xs = (-0.2, 0.0, 0.2) if cat == "rain" else (-0.12, 0.12)
        for dx in xs:
            d.line([(cx + dx * s + 0.05 * s, cy + 0.26 * s), (cx + dx * s - 0.03 * s, cy + 0.46 * s)],
                   fill=BLACK, width=w)
    elif cat == "snow":
        draw_cloud(d, cx, cy - 0.12 * s, s)
        for dx, dy in ((-0.2, 0.30), (0.0, 0.38), (0.2, 0.30), (-0.1, 0.48), (0.1, 0.48)):
            _circle(d, cx + dx * s, cy + dy * s, 0.045 * s, BLACK)
    elif cat == "thunder":
        draw_cloud(d, cx, cy - 0.12 * s, s, fill=MID)
        pts = [(0.04, 0.18), (-0.10, 0.40), (0.0, 0.40), (-0.06, 0.56), (0.14, 0.32), (0.03, 0.32), (0.10, 0.18)]
        d.polygon([(cx + x * s, cy + y * s) for x, y in pts], fill=BLACK)


def draw_drop(d, x, y, r):
    d.polygon([(x, y - 1.9 * r), (x - 0.92 * r, y), (x + 0.92 * r, y)], fill=BLACK)
    d.ellipse([x - r, y - 0.7 * r, x + r, y + 1.3 * r], fill=BLACK)


# ----------------------------------------------------------------------------
# Блок погоды
# ----------------------------------------------------------------------------
def draw_weather(d, box, wx, T, now):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    u = min(bw / 758, bh / 470)
    pad = 24 * u

    if wx is None:
        d.text((x0 + pad, y0 + pad), T["no_weather"], font=font(30 * u, True), fill=BLACK, anchor="la")
        return

    icon_s = 150 * u
    # ширина левой колонки считается по самой широкой температуре («−88°»),
    # поэтому размер цифр не зависит от текущей температуры
    worst = d.textlength("−88°", font=font(120 * u, True))
    lw = min(bw * 0.74, pad + worst + 16 * u + 0.96 * icon_s + 14 * u)
    split = x0 + lw
    left_w = lw - pad - 10 * u

    d.text((x0 + pad, y0 + pad), wx["name"], font=fit_font(d, wx["name"], left_w, 36 * u, True),
           fill=BLACK, anchor="la")

    cur = wx["current"]
    cat = wmo_category(cur["weather_code"])
    ty = y0 + pad + 56 * u
    temp = fmt_t(cur["temperature_2m"])
    tsize = 120 * u
    while tsize > 70 * u and (pad + d.textlength(temp, font=font(tsize, True)) + 16 * u + 0.96 * icon_s) > left_w + pad:
        tsize -= 4 * u
    ft = font(tsize, True)
    tw = d.textlength(temp, font=ft)
    d.text((x0 + pad, ty + (120 * u - tsize) * 0.5), temp, font=ft, fill=BLACK, anchor="la")
    draw_icon(d, cat, x0 + pad + tw + 16 * u + 0.46 * icon_s, ty + 66 * u, icon_s)
    desc = T["weather"].get(cat, "")
    d.text((x0 + pad, ty + 128 * u), desc, font=fit_font(d, desc, left_w, 30 * u, True, 20 * u),
           fill=BLACK, anchor="la")
    extra = (f"{T['feels']} {fmt_t(cur.get('apparent_temperature'))}  ·  "
             f"{T['wind']} {cur['wind_speed_10m']:.0f} {T['ms']}  ·  {cur['relative_humidity_2m']:.0f}%")
    d.text((x0 + pad, ty + 168 * u), extra, font=fit_font(d, extra, left_w, 22 * u, False, 14 * u),
           fill=DARK, anchor="la")

    # разделитель и правая колонка: день недели и дата
    d.line([(split, y0 + 16 * u), (split, y0 + 270 * u)], fill=MID, width=max(1, int(2 * u)))
    rcx = (split + x1) / 2
    rw = x1 - split - 2 * pad
    wd = T["weekdays"][now.weekday()]
    dt_txt = f"{now.day} {T['months'][now.month - 1]}"
    d.text((rcx, y0 + 88 * u), wd, font=fit_font(d, wd, rw, 64 * u, True, 24 * u), fill=BLACK, anchor="mm")
    d.text((rcx, y0 + 150 * u), dt_txt, font=fit_font(d, dt_txt, rw, 40 * u, False, 20 * u), fill=BLACK, anchor="mm")
    d.text((rcx, y0 + 196 * u), str(now.year), font=fit_font(d, str(now.year), rw, 30 * u, False, 18 * u),
           fill=DARK, anchor="mm")

    fy = y0 + 285 * u
    d.line([(x0 + pad, fy), (x1 - pad, fy)], fill=MID, width=max(1, int(2 * u)))
    daily = wx["daily"]
    n = min(5, len(daily["time"]))
    cw = (bw - 2 * pad) / max(n, 1)
    for i in range(n):
        cx = x0 + pad + cw * (i + 0.5)
        dt = datetime.fromisoformat(daily["time"][i])
        label = T["today"] if i == 0 else T["weekdays"][dt.weekday()]
        d.text((cx, fy + 8 * u), label, font=font(22 * u, True), fill=BLACK, anchor="ma")
        draw_icon(d, wmo_category(daily["weather_code"][i]), cx, fy + 66 * u, 56 * u)
        d.text((cx, fy + 98 * u), fmt_t(daily["temperature_2m_max"][i]), font=font(24 * u, True),
               fill=BLACK, anchor="ma")
        d.text((cx, fy + 124 * u), fmt_t(daily["temperature_2m_min"][i]), font=font(22 * u),
               fill=DARK, anchor="ma")
        p = daily["precipitation_probability_max"][i]
        if p is not None:
            txt = f"{int(p)}%"
            f = font(18 * u)
            tw = d.textlength(txt, font=f)
            r = 5 * u
            total = 2 * r + 5 * u + tw
            sx = cx - total / 2
            draw_drop(d, sx + r, fy + 160 * u, r)
            d.text((sx + 2 * r + 5 * u, fy + 150 * u), txt, font=f, fill=DARK, anchor="la")


# ----------------------------------------------------------------------------
# Блок отключений
# ----------------------------------------------------------------------------
def draw_bar(d, x, y, w, h, day, now_min, T, u):
    d.rectangle([x, y, x + w, y + h], fill=WHITE)
    for hr in range(3, 24, 3):
        gx = x + w * hr / 24
        d.line([(gx, y), (gx, y + h)], fill=LIGHT, width=1)
    if day["known"]:
        for s, e, kind in day["slots"]:
            xs, xe = x + w * s / 1440, x + w * e / 1440
            d.rectangle([xs, y, xe, y + h], fill=(MID if kind == "possible" or day.get("stale") else BLACK))
    d.rectangle([x, y, x + w, y + h], outline=BLACK, width=max(1, int(2 * u)))
    for hr in range(0, 25, 3):
        tx = x + w * hr / 24
        d.line([(tx, y + h), (tx, y + h + 5 * u)], fill=BLACK, width=max(1, int(2 * u)))
    if now_min is not None:
        nx = x + w * now_min / 1440
        d.line([(nx, y), (nx, y + h)], fill=BLACK, width=max(3, int(6 * u)))
        d.line([(nx, y), (nx, y + h)], fill=WHITE, width=max(1, int(2 * u)))
        d.polygon([(nx - 7 * u, y - 9 * u), (nx + 7 * u, y - 9 * u), (nx, y - 1 * u)], fill=BLACK)


def draw_group(d, x, y, w, u, g, data, now_min, T):
    label = g.get("label") or ""
    gid = str(g["group"])
    f_label, f_grp = font(30 * u, True), font(22 * u)
    cursor = x
    if label:
        d.text((x, y), label, font=f_label, fill=BLACK, anchor="la")
        cursor = x + d.textlength(label, font=f_label)
        grp = f"  {T['group_abbr']} {gid}"
    else:
        grp = f"{T['group_abbr']} {gid}"
    d.text((cursor, y + 8 * u), grp, font=f_grp, fill=DARK, anchor="la")
    left_w = cursor + d.textlength(grp, font=f_grp) - x

    if data is None:
        d.text((x, y + 48 * u), T["group_missing"], font=font(20 * u), fill=DARK, anchor="la")
        return

    kind, when = power_status(data["today"], data["tomorrow"], now_min)
    emergency = data["today"]["emergency"] or data["tomorrow"]["emergency"]
    offline = data["today"].get("offline") or data["tomorrow"].get("offline")
    if not (emergency or offline):
        if kind == "off":
            text = T["off_until"].format(t=fmt_clock(when, T))
        elif kind == "on":
            text = T["on_until"].format(t=fmt_clock(when, T))
        else:
            text = T["none"]
        f_st = fit_font(d, text, w - left_w - 40 * u, 24 * u, True, 14 * u)
        tw = d.textlength(text, font=f_st)
        xr = x + w
        if kind == "off":
            d.rectangle([xr - tw - 20 * u, y, xr, y + 34 * u], fill=BLACK)
            d.text((xr - 10 * u, y + 4 * u), text, font=f_st, fill=WHITE, anchor="ra")
        else:
            d.text((xr, y + 4 * u), text, font=f_st, fill=BLACK, anchor="ra")

    ry = y + 46 * u
    for key in ("today", "tomorrow"):
        day = data[key]
        f_l = font(19 * u, True)
        d.text((x, ry), T[key], font=f_l, fill=BLACK, anchor="la")
        lx = x + d.textlength(T[key], font=f_l) + 12 * u
        txt = intervals_text(day, T)
        f_t = fit_font(d, txt, x + w - lx, 19 * u, False, 13 * u)
        d.text((lx, ry), ellipsize(d, txt, f_t, x + w - lx), font=f_t, fill=DARK, anchor="la")
        draw_bar(d, x, ry + 31 * u, w, 30 * u, day, now_min if key == "today" else None, T, u)
        ry += 72 * u
    last_bar_bottom = ry - 72 * u + 31 * u + 30 * u
    f_tick = font(15 * u)
    for hr in range(0, 25, 3):
        d.text((x + w * hr / 24, last_bar_bottom + 7 * u), str(hr), font=f_tick, fill=DARK, anchor="ma")


def draw_outages(d, box, outs, cfg, T, now):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    groups = cfg["groups"]
    emergency = bool(outs) and any(
        v and (v["today"]["emergency"] or v["tomorrow"]["emergency"]) for v in outs.values())
    offline = bool(outs) and any(v and v["today"].get("offline") for v in outs.values())
    banner = T["offline"] if offline else (T["emergency"] if emergency else None)
    n = len(groups)
    u = min(bw / 758, bh / (56 + 212 * n + (48 if banner else 0)))
    pad = 24 * u

    y = y0 + 10 * u
    d.text((x0 + pad, y), T["outages"], font=font(28 * u, True), fill=BLACK, anchor="la")
    y += 46 * u
    if outs is None:
        d.text((x0 + pad, y), T["no_outage_data"], font=font(26 * u, True), fill=DARK, anchor="la")
        return
    if banner:
        d.rectangle([x0 + pad, y, x1 - pad, y + 38 * u], fill=BLACK)
        f = fit_font(d, banner, bw - 2 * pad - 20 * u, 20 * u, True, 12 * u)
        d.text(((x0 + x1) / 2, y + 19 * u), banner, font=f, fill=WHITE, anchor="mm")
        y += 48 * u
    now_min = now.hour * 60 + now.minute
    for g in groups:
        draw_group(d, x0 + pad, y, bw - 2 * pad, u, g, outs.get(str(g["group"])), now_min, T)
        y += 212 * u


# ----------------------------------------------------------------------------
# Сборка картинки
# ----------------------------------------------------------------------------
def render(cfg, wx, outs, errors, now):
    T = I18N.get(cfg["language"], I18N["ru"])
    W, H = cfg["screen"]["width"], cfg["screen"]["height"]
    rot = int(cfg["screen"].get("rotate", 0)) % 360
    cw, ch = (H, W) if rot in (90, 270) else (W, H)

    img = Image.new("L", (cw, ch), WHITE)
    d = ImageDraw.Draw(img)
    s = min(cw, ch) / 758
    foot = 30 * s

    if ch >= cw:  # портрет: погода сверху, отключения снизу
        split = (ch - foot) * 0.47
        draw_weather(d, (0, 0, cw, split), wx, T, now)
        d.line([(16 * s, split), (cw - 16 * s, split)], fill=BLACK, width=max(2, int(3 * s)))
        draw_outages(d, (0, split, cw, ch - foot), outs, cfg, T, now)
    else:         # ландшафт: две колонки
        half = cw / 2
        draw_weather(d, (0, 0, half, ch - foot), wx, T, now)
        d.line([(half, 16 * s), (half, ch - foot - 8 * s)], fill=BLACK, width=max(2, int(3 * s)))
        draw_outages(d, (half, 0, cw, ch - foot), outs, cfg, T, now)

    src = f"Open-Meteo / {wx['label']}" if wx and wx.get("label", "Open-Meteo") != "Open-Meteo" else "Open-Meteo"
    foot_txt = f"{T['updated']}: {now.strftime('%d.%m %H:%M')}  ·  {src}  ·  Yasno"
    if errors:
        foot_txt += "  ·  ! " + ", ".join(errors)
    d.text((cw / 2, ch - foot / 2), foot_txt, font=font(16 * s), fill=DARK, anchor="mm")

    if rot:
        img = img.rotate(rot, expand=True)
    return img


def demo_data(now):
    days = [(now.date() + timedelta(days=i)).isoformat() for i in range(5)]
    wx = {
        "name": "Киев", "label": "DWD ICON",
        "current": {"temperature_2m": 4.6, "apparent_temperature": 1.8, "weather_code": 2,
                    "wind_speed_10m": 4.2, "relative_humidity_2m": 81},
        "daily": {"time": days, "weather_code": [2, 61, 3, 71, 95],
                  "temperature_2m_max": [6, 8, 5, 0, -1], "temperature_2m_min": [2, 4, 0, -4, -5],
                  "precipitation_probability_max": [20, 70, 10, 60, 85]},
    }

    def day(slots, known=True, emergency=False):
        return {"known": known, "emergency": emergency,
                "slots": [(a * 60, b * 60, "definite") for a, b in slots]}

    outs = {
        "7.1": {"today": day([(2, 6), (11, 15), (20, 24)]), "tomorrow": day([(0, 4), (16, 20)])},
        "5.1": {"today": day([(6, 10), (15, 19)]), "tomorrow": day([], known=False)},
    }
    return wx, outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--output", help="путь к PNG (переопределяет config.json)")
    ap.add_argument("--state-in", help="файл state.json с прошлого запуска (по умолчанию рядом с PNG)")
    ap.add_argument("--demo", action="store_true", help="демо-данные без запросов в сеть")
    args = ap.parse_args()

    cfg = load_config(args.config)
    now = datetime.now(ZoneInfo(cfg["timezone"]))
    errors = []

    if args.demo:
        wx, outs = demo_data(now)
        outs = {g["group"]: v for g, v in zip(cfg["groups"], outs.values())}
    else:
        wx = outs = None
        out_path = Path(args.output or cfg["output"])
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        state_file = out_path.parent / "state.json"
        state = load_state(Path(args.state_in) if args.state_in else state_file)
        try:
            wx = fetch_weather(cfg)
        except Exception as e:  # noqa: BLE001
            errors.append("погода")
            print(f"[!] Погода: {e!r}", file=sys.stderr)
        yasno_ok = False
        try:
            outs = build_outages(fetch_outages(cfg), cfg["groups"], state, now)
            yasno_ok = True
        except Exception as e:  # noqa: BLE001
            errors.append("Yasno")
            print(f"[!] Yasno: {e!r}", file=sys.stderr)
            outs = outages_from_state(cfg["groups"], state, now)
        if wx is None and not yasno_ok:
            print("[!] Оба источника недоступны, картинка не обновлена", file=sys.stderr)
            return 1
        # state.json публикуется вместе с PNG, поэтому пишем его в любом случае
        save_state(state_file, state)

    img = render(cfg, wx, outs, errors, now)
    out = Path(args.output or cfg["output"])
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    print(f"OK: {out} ({img.size[0]}x{img.size[1]}, mode {img.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
