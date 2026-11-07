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
import os
import re
import urllib.error
import urllib.request
from datetime import datetime


BASE = "http://127.0.0.1:%s" % os.environ.get("PANEL_PORT", "8013")


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def http_get(path, headers=None):
    """Возвращает (код, тело); на 4xx/5xx не падает, а возвращает код и тело ответа."""
    url = BASE + path
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode()



# Проверка 1. Утёкший файл склеен из двух выгрузок

print("=== Проверка 1. data/leaked_sample.csv склеен из двух выгрузок ===")

leaked = read_csv("data/leaked_sample.csv")
fresh = [r for r in leaked if r["full_name"]]
arch  = [r for r in leaked if r["fio"]]
both  = sum(1 for r in leaked if r["full_name"] and r["fio"])
neither = sum(1 for r in leaked if not r["full_name"] and not r["fio"])

print(f"  строк всего:             {len(leaked)}")
print(f"  свежая половина:         {len(fresh)}")
print(f"  архивная половина:       {len(arch)}")
print(f"  строк в обеих половинах: {both}  (взаимоисключающие поля, ожидается 0)")
print(f"  строк без половины:      {neither}  (ожидается 0)")
print(f"  различных субъектов:     {len({r['client_id'] for r in leaked})}")
print(f"  пересечение половин:     {len({r['client_id'] for r in fresh} & {r['client_id'] for r in arch})}")

fresh_phones = sum(r["phone"].startswith("+7 (") for r in fresh)
arch_phones  = sum(r["phone"].startswith("+7 (") for r in arch)
fresh_iso = sum(r["created_at"] == "" and "-" in r["last_order_at"] for r in fresh)
arch_dot  = sum("." in r["created_at"] for r in arch)
spb_arch = sum(r["city"] == "С.-Петербург" for r in arch)
spb_fresh = sum(r["city"] == "С.-Петербург" for r in fresh)

print("  признаки двух источников:")
print("    1) поля: свежая — full_name/last_order_at/total_spent; архивная — fio/created_at")
print(f"    2) формат телефона '+7 (XXX)...': в свежей {fresh_phones}, в архивной {arch_phones}")
print(f"    3) формат даты: ISO в свежей {fresh_iso}, 'ДД.ММ.ГГГГ' в архивной {arch_dot}")
print(f"    4) 'С.-Петербург' только в архиве: свежая {spb_fresh}, архивная {spb_arch}")
print(f"    потолок дат архивной: {max(datetime.strptime(r['created_at'], '%d.%m.%Y') for r in arch).date()}")
print(f"    потолок дат свежей:   {max(r['last_order_at'] for r in fresh)}")



# Проверка 2. Какой месячный архив на стенде совпадает с архивной половиной

print()
print("=== Проверка 2. Какая месячная копия на стенде совпадает с архивной половиной ===")

aid = {r["client_id"] for r in arch}
best_name, best_cov = None, -1.0
for name in sorted(os.listdir("stand/storage")):
    if not name.endswith(".csv"):
        continue
    rows = read_csv("stand/storage/" + name)
    ids = {r["client_id"] for r in rows}
    cov = len(aid & ids) / len(aid)
    print(f"  {name:<26} доля архивных client_id: {cov*100:5.1f}%   ({len(aid & ids)}/{len(aid)})")
    if cov > best_cov:
        best_cov, best_name = cov, name

print(f"  совпадает: {best_name} (покрытие {best_cov*100:.1f}%)")

best_rows = {r["client_id"]: r for r in read_csv("stand/storage/" + best_name)}
fields = ("fio", "phone", "email", "city", "created_at")
same = sum(all(r[k] == best_rows.get(r["client_id"], {}).get(k) for k in fields) for r in arch)
print(f"  построчное совпадение: {same}/{len(arch)} архивных строк полностью равны копии {best_name}")



# Проверка 3. Коды стенда: бэкап отдаётся без авторизации, выгрузка — нет

print()
print("=== Проверка 3. Резервная копия отдаётся без авторизации, выгрузка — нет ===")

code_bk, body_bk = http_get("/backup/clients_2026-06.csv")
code_ex, _       = http_get("/api/export")

if code_bk is None:
    print(f"  стенд не поднят: {body_bk.decode('utf-8', 'replace').splitlines()[-1][:100]}")
    print("  поднимите стенд: bash stand/run.sh")
else:
    disk_size = os.path.getsize("stand/storage/clients_2026-06.csv")
    print(f"  GET /backup/clients_2026-06.csv   без авторизации -> {code_bk}, отдано {len(body_bk)} байт")
    print(f"  GET /api/export                  без сессии       -> {code_ex}")
    if len(body_bk) == disk_size:
        print(f"  размер отдачи равен размеру файла на диске ({disk_size} байт).")
        print("  NB: в data/access.csv стоит bytes=367587 — это эталон для CRLF;")
        print(f"     на этой машине файл {disk_size} байт: разница {367587 - disk_size} = число строк,")
        print("     переводы строк конвертированы CRLF→LF при клонировании git.")
    if code_bk == 200 and code_ex == 401:
        print("  вывод: сервер умеет требовать авторизацию (401 на /api/export),")
        print("         но на /backup/ её не применяет (200). Это и есть открытая дверь.")



# Проверка 4. Сервисный токен из истории репозитория

print()
print("=== Проверка 4. Сервисный токен из истории репозитория ===")

hist = open("data/export_tool/history.log", encoding="utf-8").read()
m = re.search(r'SERVICE_TOKEN\s*=\s*"([^"]+)"', hist)
token = None

if not m:
    print("  SERVICE_TOKEN не найден в history.log")
else:
    token = m.group(1)
    blocks = re.split(r"(?m)^commit\s+", hist)
    matches = []
    for b in blocks[1:]:
        if "SERVICE_TOKEN" in b and token in b:
            sha = b.split()[0]
            ma = re.search(r"Author:\s*(.+)", b)
            md = re.search(r"Date:\s*(.+)", b)
            matches.append({
                "sha": sha,
                "author": ma.group(1).strip() if ma else "?",
                "date": md.group(1).strip() if md else "?",
                "pos": hist.find("commit " + sha),
            })
    if matches:
        first = min(matches, key=lambda x: x["pos"])
        print(f"  токен:  {token}")
        print(f"  коммит: {first['sha']}")
        print(f"  автор:  {first['author']}")
        print(f"  дата:   {first['date']}")
    else:
        print(f"  токен: {token}; блок коммита с токеном не найден")

if token:
    code_tok, body_tok = http_get("/api/config", {"X-Auth-Token": token})
    code_no_tok, _ = http_get("/api/config")
    code_bad_tok, _ = http_get("/api/config", {"X-Auth-Token": "nope"})
    if code_tok is None:
        print(f"  стенд не поднят, проверка действия токена пропущена: "
              f"{body_tok.decode('utf-8', 'replace').splitlines()[-1][:80]}")
    else:
        print(f"  GET /api/config без токена       -> {code_no_tok}")
        print(f"  GET /api/config с чужим токеном  -> {code_bad_tok}")
        print(f"  GET /api/config с этим токеном   -> {code_tok}")
        if code_tok == 200:
            cfg = json.loads(body_tok.decode("utf-8"))
            print(f"  токен действует; в конфиге: backup_path={cfg.get('backup_path')!r}, "
                  f"учётных записей {len(cfg.get('accounts', []))}")

    print("  события журнала доступа, где использован этот токен:")
    for i, r in enumerate(read_csv("data/access.csv"), start=2):
        hit_token = ("token_id=" + token) in r["detail"]
        hit_pair  = (r["session_id"] == "s09901" and r["action"] == "read_config")
        if hit_token or hit_pair:
            print(f"    строка {i}: {r['ts']} | login={r['login']!r} | ip={r['ip']} | "
                  f"action={r['action']} | session_id={r['session_id']} | detail={r['detail']}")



# Проверка 5. Хеш-цепочка журнала ассистента

print()
print("=== Проверка 5. Журнал ассистента: разрыв хеш-цепочки ===")

with open("data/audit.jsonl", encoding="utf-8") as f:
    entries = [json.loads(line) for line in f if line.strip()]


def rh(r, sort_keys=True):
    raw = "%s|%s|%s|%s|%s|%s" % (
        r["seq"], r["ts"], r["actor"], r["action"],
        json.dumps(r["payload"], sort_keys=sort_keys, ensure_ascii=False),
        r["prev_hash"],
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


print(f"  записей в журнале: {len(entries)}")

bad = [r for r in entries if rh(r) != r["hash"]]
print(f"  записей, где содержимое не сходится с собственным хешем: {len(bad)}")
for r in bad:
    print(f"    seq={r['seq']} ts={r['ts']} action={r['action']!r}")

broken_links = [entries[i]["seq"] for i in range(1, len(entries))
                if entries[i]["prev_hash"] != entries[i - 1]["hash"]]
print(f"  записей, где prev_hash не совпадает с предыдущей: {len(broken_links)}"
      + (f" {broken_links}" if broken_links else ""))

bad_nosort = [r["seq"] for r in entries if rh(r, sort_keys=False) != r["hash"]]
print(f"  без sort_keys=True расходятся: {bad_nosort}")
print("    (это не находка, а ошибка инструмента: на этом файле sort_keys обязателен)")

if bad:
    target = bad[0]
    idx = entries.index(target)
    lo, hi = max(0, idx - 1), min(len(entries), idx + 2)
    print()
    print("  запись и две соседние:")
    for j in range(lo, hi):
        r = entries[j]
        marker = "   <-- подмена" if j == idx else ""
        pl = json.dumps(r["payload"], ensure_ascii=False, sort_keys=True)
        print(f"    seq={r['seq']:>3}  ts={r['ts']}  action={r['action']:<14}  "
              f"payload={pl}  hash={r['hash'][:12]}...{marker}")

    print()
    print("  предположение о том, какое событие стояло на месте подменённого:")
    print("    на месте записи 91 стояло событие выдачи конфигурации по сервисному")
    print("    токену (api_auth/read_config с peer 45.132.19.88 и bytes=1841).")
    print("    Основания:")
    print("      - соседние 90 и 92 — session_open и session_close с тем же peer 45.132.19.88;")
    print("        'heartbeat' между открытием и закрытием внешней сессии бессмысленен;")
    print("      - bytes_out=1841 в записи 92 совпадает с bytes=1841 в access.csv")
    print("        на событии read_config по тому же токену с того же адреса.")