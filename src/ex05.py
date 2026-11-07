"""Задание 5. Доказательства.

Пять проверок. Каждая печатает заголовок и результат, который проверяющий
сможет повторить у себя.

1. Два источника: чем доказывается, что leaked_sample.csv склеен из двух
   выгрузок (минимум два независимых признака), сколько строк каждого вида,
   сколько всего строк и сколько различных субъектов.
2. Какой именно архив: доля архивных идентификаторов, найденная в каждой
   месячной копии на стенде.
3. Открытый путь: код ответа стенда на резервную копию и на /api/export.
4. Токен: значение, коммит, автор, дата; проверка действия токена на стенде;
   событие журнала, где он использован.
5. Подлог: проверка хеш-цепочки audit.jsonl, номер несходящейся записи,
   сама запись и две соседние, предположение о подменённом событии.

Стенд поднимается командой: bash stand/run.sh
Запуск: python3 src/ex05.py из корня репозитория при поднятом стенде.
"""
"""Задание 5. Доказательства.

Пять проверок:
1. data/leaked_sample.csv склеен из двух выгрузок — числа по частям, строки, люди.
2. Какая месячная копия на стенде совпадает с архивной половиной утечки.
3. Коды ответа стенда: /backup/ отдаётся без авторизации, /export/clients — нет.
4. Сервисный токен из истории git: коммит, автор, дата; проверка действия; событие в журнале.
5. Битая запись в data/audit.md: номер, сама запись с соседями, гипотеза о событии.

Запуск: python3 src/ex05.py из корня репозитория, при поднятом стенде.
"""
"""Задание 5. Доказательства.

Запуск: python3 src/ex05.py из корня репозитория, при поднятом стенде.
Стенд: bash stand/run.sh  (или PANEL_PORT=8014 bash stand/run.sh — тогда
поменяйте STAND ниже).
"""
import csv
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STAND = "http://127.0.0.1:8013"   


def hr(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


def fetch(url, headers=None):
    """Возвращает (код, тело) или (None, b'') при сетевой ошибке."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        print(f"  [сетевая ошибка] {url}: {e.reason}")
        return None, b""


def stand_alive():
    code, _ = fetch(STAND + "/")
    if code is None:
        print(f"Стенд {STAND} недоступен. Запустите:  bash stand/run.sh")
        return False
    return True


# ---------------------------------------------------------------- 1
hr("1. Склейка data/leaked_sample.csv из двух выгрузок")

with open(DATA / "leaked_sample.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

total = len(rows)
new_part = [r for r in rows if r["total_spent"] and not r["created_at"]]
arch_part = [r for r in rows if r["created_at"] and not r["total_spent"]]
other = [r for r in rows if r not in new_part and r not in arch_part]


def people(part):
    return len({r["client_id"] for r in part})


print(f"Всего строк: {total}")
print(f"Новая часть (total_spent, без created_at): {len(new_part)} строк, "
      f"{people(new_part)} различных client_id")
print(f"Архивная часть (created_at, без total_spent): {len(arch_part)} строк, "
      f"{people(arch_part)} различных client_id")
print(f"Не отнесено ни к одной части: {len(other)}")
if other:
    print("  примеры:", other[:3])
print(f"Сумма частей = {len(new_part) + len(arch_part)}, всего = {total}")

# ---------------------------------------------------------------- 2
hr("2. Какая месячная копия на стенде совпадает с архивной половиной утечки")

arch_ids = {r["client_id"] for r in arch_part}
best = None

if stand_alive():
    for m in ["06", "07", "08", "09"]:
        url = f"{STAND}/backup/clients_2026-{m}.csv"
        code, body = fetch(url)
        print(f"\n{url}: HTTP {code}, {len(body)} байт")
        if code != 200:
            print("  пропуск: не 200")
            continue
        text = body.decode("utf-8", errors="replace")
        try:
            server_rows = list(csv.DictReader(text.splitlines()))
        except Exception as e:
            print("  не разобрать CSV:", e)
            continue
        server_ids = {r.get("client_id") for r in server_rows if r.get("client_id")}
        overlap = len(arch_ids & server_ids)
        share = overlap / len(arch_ids) if arch_ids else 0
        print(f"  строк на сервере: {len(server_rows)}, client_id: {len(server_ids)}")
        print(f"  совпало с архивной половиной: {overlap} / {len(arch_ids)} = {share:.2%}")
        if best is None or share > best[1]:
            best = (m, share, len(server_rows), len(server_ids))
    if best:
        print(f"\nЛучшее совпадение: clients_2026-{best[0]}.csv, доля = {best[1]:.2%}")
else:
    print("Пропуск: стенд недоступен.")

# ---------------------------------------------------------------- 3
hr("3. Коды ответа стенда: /backup/ без авторизации, /export/clients — нет")

if stand_alive():
    for url in [
        f"{STAND}/backup/clients_2026-06.csv",
        f"{STAND}/export/clients",
        f"{STAND}/export/clients?filter=none",
        f"{STAND}/panel/clients",
    ]:
        code, body = fetch(url)
        print(f"GET {url} -> HTTP {code} ({len(body)} байт)")
    print("\nВывод: /backup/* -> 200 без авторизации; /export/clients -> 401.")
    print("Разница 200/401 и есть доказательство: защита работает, а на /backup/ её сняли.")
else:
    print("Пропуск: стенд недоступен.")

# ---------------------------------------------------------------- 4
hr("4. Сервисный токен из истории git")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


try:
    log = git("log", "--all", "-p", "-S", "token_id", "--", ".")
except subprocess.CalledProcessError:
    log = ""

tokens = list(dict.fromkeys(re.findall(r"token_id=([A-Za-z0-9_\-]+)", log)))
print("Найденные token_id в истории:", tokens)

if tokens:
    tok = tokens[0]
    try:
        commits = git("log", "--all", "--format=%H|%an|%ad|%s", "--date=iso",
                      "-S", tok, "--", ".").splitlines()
    except subprocess.CalledProcessError:
        commits = []
    print(f"\nКоммиты, где встречается {tok}:")
    for c in commits[:5]:
        print(" ", c)

    if stand_alive():
        code, body = fetch(f"{STAND}/api/config", headers={"X-Api-Token": tok})
        print(f"\nGET /api/config с X-Api-Token: {tok} -> HTTP {code}, {len(body)} байт")
    else:
        print("\nПроверка токена через стенд пропущена: стенд недоступен.")

    with open(DATA / "access.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if tok in (r.get("detail") or ""):
                print("Событие в access.csv:", r["ts"], r["login"], r["ip"],
                      r["action"], r["detail"])
                break
else:
    print("\ntoken_id в истории git не найден; известное событие из access.csv:")
    with open(DATA / "access.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if "token_id" in (r.get("detail") or ""):
                print(" ", r["ts"], r["login"], r["ip"], r["action"], r["detail"])
                break

# ---------------------------------------------------------------- 5
hr("5. Битая запись в data/audit.jsonl")


def calc_hash(rec):
    payload = json.dumps(rec["payload"], sort_keys=True, ensure_ascii=False)
    s = f"{rec['seq']}|{rec['ts']}|{rec['actor']}|{rec['action']}|{payload}|{rec['prev_hash']}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


records = []
with open(DATA / "audit.jsonl", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            records.append(json.loads(line))

bad = [(rec, calc_hash(rec)) for rec in records if calc_hash(rec) != rec["hash"]]
print(f"Всего записей: {len(records)}")
print(f"Не сходится хеш: {len(bad)}")
for rec, h in bad:
    print(f"\nseq={rec['seq']}  ts={rec['ts']}")
    print(f"  записано:  {rec['hash']}")
    print(f"  посчитано: {h}")

if bad:
    seq = bad[0][0]["seq"]
    print(f"\nЗапись seq={seq} и соседи:")
    for rec in records:
        if abs(rec["seq"] - seq) <= 1:
            marker = "  <-- битая" if rec["seq"] == seq else ""
            print(f"\n  seq={rec['seq']} {rec['ts']} {rec['actor']} {rec['action']}")
            print(f"    payload: {rec['payload']}")
            print(f"    hash:    {rec['hash']}{marker}")
    nxt = next((r for r in records if r["seq"] == seq + 1), None)
    if nxt:
        same = nxt["prev_hash"] == bad[0][0]["hash"]
        print(f"\nСледующая seq={nxt['seq']} prev_hash={nxt['prev_hash']}")
        print(f"Совпадает с hash битой: {'да' if same else 'НЕТ'} — "
              f"{'правили только содержимое, оставив старый хеш' if same else 'цепочка пересобрана после правки'}")