"""Задание 3. Хронология и алиби.

1. Хронология ночи инцидента: 11.09 18:00 — 12.09 06:00 по московскому времени.
   Время приведено, город получен соединением со справочником адресов.
2. Для каждой учётной записи — расстояние, время и требуемая скорость
   между соседними входами. Формула гаверсинуса — в materials/logs_rus.md.
3. Печать всех пар, где требуемая скорость выше 900 км/ч.
4. Вывод: чья учётная запись использовалась более чем одним человеком,
   какая сессия сделала выгрузку, какая не могла принадлежать владельцу.
5. Что именно неверно в data/watcher_report.md: номер основания
   и событие журнала, которое ему противоречит.

Запуск: python3 src/ex03.py из корня репозитория.
"""
"""Задание 3. Хронология и алиби.

Запуск: python3 src/ex03.py из корня репозитория.
"""
import csv
import math
import sqlite3
from datetime import datetime

con = sqlite3.connect(":memory:")
cur = con.cursor()
cur.execute("""
CREATE TABLE access (
    ts TEXT, login TEXT, ip TEXT, action TEXT, object TEXT,
    result TEXT, auth_method TEXT, session_id TEXT, detail TEXT
)""")
cur.execute("""CREATE TABLE geoip (ip TEXT, city TEXT, lat REAL, lon REAL, org TEXT)""")

for table, path in (("access", "data/access.csv"), ("geoip", "data/geoip.csv")):
    with open(path, encoding="utf-8") as f:
        rows = [tuple(r.values()) for r in csv.DictReader(f)]
    marks = ",".join("?" * len(rows[0]))
    cur.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
con.commit()


def portm(s: str) -> str:
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    raise ValueError(f"bad ts: {s!r}")


con.create_function("portm", 1, portm)
cur.execute("""CREATE VIEW v AS
SELECT portm(ts) AS ts, login, ip, action, object, result,
       auth_method, session_id, detail
FROM access""")


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


print("=== Хронология 11.09 18:00 — 12.09 06:00 MSK ===\n")
rows = cur.execute("""
SELECT v.ts, v.login, g.city, v.ip, v.action, v.session_id, v.detail
FROM v JOIN geoip g ON v.ip = g.ip
WHERE v.ts BETWEEN '2026-09-11 18:00:00' AND '2026-09-12 06:00:00'
ORDER BY v.ts
""").fetchall()
for ts, login, city, ip, action, sid, detail in rows:
    print(f"{ts}  {login:<10} {city:<13} {ip:<16} {action:<14} {sid}  {detail}")

print("\n=== Невозможные перемещения (соседние входы одной учётки) ===\n")

logins = cur.execute("""
SELECT v.ts, v.login, v.ip, g.lat, g.lon, g.city
FROM v JOIN geoip g ON v.ip = g.ip
WHERE v.action = 'login' AND v.result = 'ok'
ORDER BY v.login, v.ts
""").fetchall()

by_login = {}
for ts, login, ip, lat, lon, city in logins:
    by_login.setdefault(login, []).append((ts, ip, lat, lon, city))

problems = []
for login, events in by_login.items():
    for (t1, ip1, la1, lo1, c1), (t2, ip2, la2, lo2, c2) in zip(events, events[1:]):
        d = haversine(la1, lo1, la2, lo2)
        dt = (datetime.strptime(t2, "%Y-%m-%d %H:%M:%S")
              - datetime.strptime(t1, "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600
        if dt <= 0:
            continue
        speed = d / dt
        if speed > 900:  
            problems.append((login, t1, c1, ip1, t2, c2, ip2, d, dt * 60, speed))
            print(f"{login:<10} {t1} {c1:<12} ({ip1})  ->  "
                  f"{t2} {c2:<12} ({ip2})  "
                  f"dist={d:7.1f} км  dt={dt*60:5.1f} мин  v={speed:8.0f} км/ч")


print("\n=== Итог по сессиям ===\n")


night_sessions = cur.execute("""
SELECT session_id, login, MIN(ts), MAX(ts), GROUP_CONCAT(DISTINCT ip),
       GROUP_CONCAT(DISTINCT action)
FROM v
WHERE ts BETWEEN '2026-09-11 18:00:00' AND '2026-09-12 06:00:00'
GROUP BY session_id
ORDER BY MIN(ts)
""").fetchall()
for sid, login, t0, t1, ips, acts in night_sessions:
    print(f"{sid}  {login:<10} {t0} .. {t1}  ips={ips}  actions={acts}")


export_sid = cur.execute("""
SELECT session_id, login, ts, ip, detail FROM v
WHERE action='export' AND ts >= '2026-09-11 18:00:00'
""").fetchall()
print("\nСессия выгрузки:", export_sid)


print("\n=== Опровержение отчёта ===\n")


detail = cur.execute("""
SELECT ts, ip, detail FROM v
WHERE login='a.sokolov' AND action='login'
  AND ts >= '2026-09-11 18:00:00' AND ts <= '2026-09-12 06:00:00'
ORDER BY ts
""").fetchall()
for ts, ip, det in detail:
    print(ts, ip, det)
print("""
Опровергнуто основание отчёта: «выгрузку сделал владелец учётной записи,
потому что вход был со всеми факторами».
Событие-контрпример: 2026-09-11 23:55:04 вход a.sokolov с 176.59.208.33
(Сочи, мобильный), а уже 2026-09-12 00:01:14 — вход с 185.220.101.45
(VPS, «Москва»): между ними 6 мин 10 с и ~1360 км. Требуемая скорость
~13 000 км/ч. Один человек так не перемещается.
Дополнительно: mfa_enrolled_at=2026-09-11T20:31:18Z в логине 00:01:14
совпадает с моментом mfa_reset (d.kravets, 20:31:18) — новый фактор
зарегистрировал не владелец, а тот, кто получил доступ после сброса.
Значит, «вход со всеми факторами» подтверждает лишь то, что кто-то
прошёл аутентификацию, а не что это был Соколов.
""")
