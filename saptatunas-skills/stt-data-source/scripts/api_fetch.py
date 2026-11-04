#!/usr/bin/env python3
"""Fetch data from Sapta Tunas internal apps through the API Gateway.

Endpoints are declared in a sources config (default ~/stt-data/sources.json,
override with --config or STT_SOURCES). Results are normalized to the same
record shape as parse_wa_export.py so all sources can be merged.

  List sources : api_fetch.py --list
  Read         : api_fetch.py tiket --param status=open --since 2026-11-01
  Raw response : api_fetch.py tiket --raw
  Write        : api_fetch.py buat_tiket --body tiket.json --confirm

Secrets are read from environment variables named in the config; they are
never printed.
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_CONFIG = os.path.expanduser(os.environ.get("STT_SOURCES", "~/stt-data/sources.json"))
NORMAL_KEYS = ["timestamp", "date", "time", "sender", "text", "ref_id", "status", "url"]


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def get_path(obj, path):
    """Dot path lookup: 'data.items', 'customer.name', 'tags.0'."""
    if path in (None, "", "."):
        return obj
    cur = obj
    for part in str(path).split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
        if cur is None:
            return None
    return cur


def env_required(name):
    v = os.environ.get(name)
    if not v:
        die(f"environment variable {name} belum diset")
    return v


def build_headers(auth, extra):
    h = {"Accept": "application/json", "User-Agent": "stt-hermes-agent/1.1"}
    h.update(extra or {})
    t = (auth or {}).get("type", "none")
    if t == "bearer":
        h["Authorization"] = "Bearer " + env_required(auth["token_env"])
    elif t == "header":
        h[auth["name"]] = env_required(auth["value_env"])
    elif t == "basic":
        cred = f"{env_required(auth['user_env'])}:{env_required(auth['pass_env'])}"
        h["Authorization"] = "Basic " + base64.b64encode(cred.encode()).decode()
    elif t != "none":
        die(f"auth type tidak dikenal: {t}")
    return h


def request(method, url, headers, body=None, timeout=30, retries=1):
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers = dict(headers, **{"Content-Type": "application/json"})
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            if e.code >= 500 and attempt < retries:
                time.sleep(2)
                continue
            detail = e.read().decode("utf-8", errors="replace")[:300]
            die(f"HTTP {e.code} dari {redact(url)}: {detail}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2)
                continue
            die(f"tidak bisa menghubungi {redact(url)}: {e.reason}")
        except json.JSONDecodeError:
            die(f"respons dari {redact(url)} bukan JSON")


def redact(url):
    return re.sub(r"(token|key|secret|password)=[^&]+", r"\1=***", url, flags=re.I)


def normalize(item, mapping, source_name):
    rec = {}
    for key, path in (mapping or {}).items():
        val = get_path(item, path)
        rec[key] = val
    ts = rec.get("timestamp")
    if isinstance(ts, str) and re.match(r"\d{4}-\d{2}-\d{2}", ts):
        rec.setdefault("date", ts[:10])
        m = re.match(r"\d{4}-\d{2}-\d{2}[T ](\d{2}:\d{2})", ts)
        if m:
            rec.setdefault("time", m.group(1))
    for k in NORMAL_KEYS:
        rec.setdefault(k, None)
    rec["source"] = f"api:{source_name}"
    if not mapping:
        rec["extra"] = item
    return rec


def fetch(cfg, name, params, timeout):
    gw = cfg.get("gateway", {})
    src = cfg["sources"][name]
    base = src.get("base_url", gw.get("base_url", "")).rstrip("/")
    if not base:
        die("base_url belum diisi di config")
    auth = src.get("auth", gw.get("auth"))
    headers = build_headers(auth, dict(gw.get("headers", {}), **src.get("headers", {})))

    path = src["path"]
    q = dict(src.get("params", {}))
    q.update(params)
    for k in list(q):  # fill {placeholders} in path
        if "{" + k + "}" in path:
            path = path.replace("{" + k + "}", urllib.parse.quote(str(q.pop(k)), safe=""))
    if re.search(r"\{[^}]+\}", path):
        die(f"parameter path belum lengkap: {path} (pakai --param nama=nilai)")

    pg = src.get("pagination", {"type": "none"})
    max_pages = int(pg.get("max_pages", 10))
    items_path = src.get("items_path", "")
    pages, items = [], []
    next_url = None
    for i in range(max_pages):
        if pg.get("type") == "page":
            q[pg.get("param", "page")] = int(pg.get("start", 1)) + i
        elif pg.get("type") == "offset":
            q[pg.get("param", "offset")] = i * int(pg.get("size", q.get("limit", 100)))
        url = next_url or (base + path + ("?" + urllib.parse.urlencode(q, doseq=True) if q else ""))
        resp = request("GET", url, headers, timeout=timeout)
        pages.append(resp)
        batch = get_path(resp, items_path) if items_path else resp
        if isinstance(batch, dict):
            batch = [batch]
        batch = batch or []
        items.extend(batch)
        t = pg.get("type", "none")
        if t == "none" or not batch:
            break
        if t == "cursor":
            nxt = get_path(resp, pg.get("next_path", "next"))
            if not nxt:
                break
            if str(nxt).startswith("http"):
                next_url = nxt
            else:
                q[pg.get("param", "cursor")] = nxt
                next_url = None
    return pages, items


def write(cfg, name, params, body, timeout):
    gw = cfg.get("gateway", {})
    src = cfg["sources"][name]
    base = src.get("base_url", gw.get("base_url", "")).rstrip("/")
    headers = build_headers(src.get("auth", gw.get("auth")), dict(gw.get("headers", {}), **src.get("headers", {})))
    path = src["path"]
    for k, v in params.items():
        path = path.replace("{" + k + "}", urllib.parse.quote(str(v), safe=""))
    return request(src.get("method", "POST").upper(), base + path, headers, body=body, timeout=timeout, retries=0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--list", action="store_true", help="tampilkan daftar sumber di config")
    ap.add_argument("--param", action="append", default=[], help="nama=nilai (query atau {placeholder} path)")
    ap.add_argument("--since", help="filter tanggal YYYY-MM-DD (di sisi klien)")
    ap.add_argument("--until", help="filter tanggal YYYY-MM-DD (di sisi klien)")
    ap.add_argument("--grep", help="regex pada field text")
    ap.add_argument("--raw", action="store_true", help="keluarkan respons mentah")
    ap.add_argument("--body", help="file JSON untuk sumber bertipe write")
    ap.add_argument("--confirm", action="store_true", help="wajib untuk operasi write")
    ap.add_argument("--timeout", type=int)
    ap.add_argument("--out")
    a = ap.parse_args()

    if not os.path.exists(a.config):
        die(f"config tidak ditemukan: {a.config} (salin dari sources.example.json)")
    cfg = json.load(open(a.config, encoding="utf-8"))
    sources = cfg.get("sources", {})

    if a.list or not a.source:
        for n, s in sources.items():
            kind = "WRITE" if s.get("write") else "read"
            print(f"{n:<22} {kind:<6} {s.get('method', 'GET'):<6} {s.get('path', '')}  — {s.get('description', '')}")
        return
    if a.source not in sources:
        die(f"sumber '{a.source}' tidak ada di config. Pakai --list.")

    params = {}
    for p in a.param:
        if "=" not in p:
            die(f"format --param harus nama=nilai: {p}")
        k, v = p.split("=", 1)
        params[k] = v
    timeout = a.timeout or cfg.get("gateway", {}).get("timeout", 30)
    src = sources[a.source]

    if src.get("write"):
        if not a.body:
            die("sumber ini bertipe write, butuh --body file.json")
        body = json.load(open(a.body, encoding="utf-8"))
        if not a.confirm:
            print(json.dumps({"dry_run": True, "source": a.source, "method": src.get("method", "POST"),
                              "path": src["path"], "params": params, "body": body}, ensure_ascii=False, indent=2))
            print("Belum dikirim. Tambahkan --confirm setelah disetujui.", file=sys.stderr)
            sys.exit(3)
        result = write(cfg, a.source, params, body, timeout)
        output = result
    else:
        pages, items = fetch(cfg, a.source, params, timeout)
        if a.raw:
            output = pages if len(pages) > 1 else pages[0]
        else:
            recs = [normalize(it, src.get("map"), a.source) for it in items]
            if a.since:
                recs = [r for r in recs if (r.get("date") or "") >= a.since]
            if a.until:
                recs = [r for r in recs if (r.get("date") or "9999") <= a.until]
            if a.grep:
                rx = re.compile(a.grep, re.I)
                recs = [r for r in recs if rx.search(str(r.get("text") or ""))]
            output = recs
            print(f"{len(recs)} record dari {a.source}", file=sys.stderr)

    text = json.dumps(output, ensure_ascii=False, indent=2)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text + "\n")
        print(f"ditulis ke {a.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
