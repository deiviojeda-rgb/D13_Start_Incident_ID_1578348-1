"""Задание 1. Журнал в SQLite.

Скопируйте сюда загрузчик из Readme и добавьте шесть запросов,
каждый со своей подписью и номером.

1. Сколько строк в журнале.
2. Сколько различных учётных записей.
3. Сколько строк в каждом формате записи времени.
4. SQL-функция norm(), приводящая время к одному виду; проверка на двух строках.
5. Все события выгрузки данных.
6. Все события, где способ аутентификации не password+mfa и не session.

Запуск: python3 src/ex01.py из корня репозитория.
"""

import csv
import sqlite3
from datetime import datetime

con = sqlite3.connect(":memory:")
cur = con.cursor()

cur.execute("""
CREATE TABLE access (
    ts TEXT, login TEXT, ip TEXT, action TEXT, object TEXT,
    result TEXT, auth_method TEXT, session_id TEXT, detail TEXT
)
""")

cur.execute("""
CREATE TABLE geoip (
    ip TEXT, city TEXT, lat REAL, lon REAL, org TEXT
)
""")

for table, path in (("access", "data/access.csv"), ("geoip", "data/geoip.csv")):
    with open(path, encoding="utf-8") as f:
        rows = [tuple(r.values()) for r in csv.DictReader(f)]
    marks = ",".join("?" * len(rows[0]))
    cur.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
con.commit()

def portm(s: str) -> str:
    """Любое из встречающихся написаний времени -> 'ГГГГ-ММ-ДД ЧЧ:ММ:СС'."""
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"неизвестный формат времени: {s!r}")

con.create_function("portm", 1, portm)


def show(title, rows, headers=None):
    print(title)
    if headers:
        print(" | ".join(headers))
    for r in rows:
        print(r)
    print()


# 1. Сколько всего строк в журнале
n = cur.execute("SELECT COUNT(*) FROM access").fetchone()[0]
show("1. Всего строк в журнале:", [(n,)])

# 2. Сколько различных значений в поле login
n = cur.execute("SELECT COUNT(DISTINCT login) FROM access").fetchone()[0]
show("2. Различных значений login:", [(n,)])

# 3. Сколько строк в каждом формате времени
#    Определяем формат по наличию точки в дате / дефиса.
rows = cur.execute("""
SELECT
    CASE
        WHEN ts LIKE '__.__.____ %' THEN 'DD.MM.YYYY HH:MM:SS'
        WHEN ts LIKE '____-__-__ %' THEN 'YYYY-MM-DD HH:MM:SS'
        ELSE 'unknown'
    END AS fmt,
    COUNT(*)
FROM access
GROUP BY fmt
ORDER BY fmt
""").fetchall()
show("3. Строк по форматам времени:", rows, ["format", "count"])

# 4. Проверка portm на двух строках разного формата
samples = [
    "2026-08-03 05:38:07",
    "03.08.2026 05:41:07",
]
checked = [(s, portm(s)) for s in samples]
show("4. Проверка portm:", checked, ["input", "output"])

# 5. Все события выгрузки данных
rows = cur.execute("""
SELECT portm(ts), login, ip, detail
FROM access
WHERE action = 'export'
ORDER BY portm(ts)
""").fetchall()
show("5. События выгрузки (export):", rows, ["ts", "login", "ip", "detail"])

# 6. События, у которых auth_method не password+mpfa и не session
#    Сначала — какие значения вообще есть:
auth_vals = cur.execute("""
SELECT auth_method, COUNT(*) FROM access GROUP BY auth_method ORDER BY 2 DESC
""").fetchall()
show("6a. Значения auth_method:", auth_vals, ["auth_method", "count"])

rows = cur.execute("""
SELECT portm(ts), login, ip, action, object, auth_method, detail
FROM access
WHERE auth_method NOT IN ('password+mpfa', 'session')
ORDER BY portm(ts)
""").fetchall()
show("6b. События с иным способом аутентификации:", rows,
     ["ts", "login", "ip", "action", "object", "auth_method", "detail"])

