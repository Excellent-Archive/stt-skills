#!/usr/bin/env python3
"""Parse WhatsApp chat export (.txt) into structured records.

Supports Android ("04/11/26 11.58 - Nama: pesan", "4/11/26, 11:58 AM - Nama: pesan")
and iPhone ("[04/11/26 11.58.03] Nama: pesan") formats, multi-line messages,
and system messages.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime

INVISIBLE = "‎‏‪‬﻿"

# iPhone: [dd/mm/yy hh.mm.ss] Sender: text
IOS = re.compile(
    r"^\[(?P<date>\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}),?\s+"
    r"(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?(?:\s?[APap]\.?[Mm]\.?)?)\]\s+"
    r"(?P<rest>.*)$"
)
# Android: dd/mm/yy hh.mm - Sender: text
ANDROID = re.compile(
    r"^(?P<date>\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}),?\s+"
    r"(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?(?:\s?[APap]\.?[Mm]\.?)?)\s+[-–]\s+"
    r"(?P<rest>.*)$"
)
MEDIA = re.compile(
    r"<media tidak disertakan>|<media omitted>|(image|video|audio|sticker|document|gif) omitted"
    r"|gambar tidak disertakan|\.(jpg|jpeg|png|pdf|opus|mp4|webp)\s*\((file|lampiran) ",
    re.I,
)
DELETED = re.compile(r"pesan ini telah dihapus|this message was deleted|you deleted this message|anda menghapus pesan ini", re.I)


def parse_dt(date_s, time_s, dayfirst=True):
    parts = re.split(r"[/.\-]", date_s)
    a, b, y = int(parts[0]), int(parts[1]), int(parts[2])
    if y < 100:
        y += 2000
    d, m = (a, b) if dayfirst else (b, a)
    if m > 12 and d <= 12:  # obviously swapped
        d, m = m, d
    t = time_s.strip().replace(".", ":").upper().replace("A:M:", "AM").replace("P:M:", "PM")
    t = re.sub(r"\s+", " ", t)
    ampm = None
    m_ap = re.search(r"([AP])\.?M\.?$", t)
    if m_ap:
        ampm = m_ap.group(1)
        t = t[: m_ap.start()].strip()
    tp = [int(x) for x in t.split(":") if x]
    hh, mm = tp[0], tp[1]
    ss = tp[2] if len(tp) > 2 else 0
    if ampm == "P" and hh < 12:
        hh += 12
    if ampm == "A" and hh == 12:
        hh = 0
    return datetime(y, m, d, hh, mm, ss)


def parse(path, dayfirst=True):
    records = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n").rstrip("\r")
            clean = line.lstrip(INVISIBLE)
            m = IOS.match(clean) or ANDROID.match(clean)
            if m:
                try:
                    ts = parse_dt(m.group("date"), m.group("time"), dayfirst)
                except (ValueError, IndexError):
                    ts = None
                if ts:
                    rest = m.group("rest").lstrip(INVISIBLE)
                    if ": " in rest:
                        sender, text = rest.split(": ", 1)
                        is_system = False
                    else:
                        sender, text, is_system = "", rest, True
                    records.append({
                        "timestamp": ts.isoformat(),
                        "date": ts.date().isoformat(),
                        "time": ts.strftime("%H:%M"),
                        "sender": sender.strip(INVISIBLE + " "),
                        "text": text.strip(INVISIBLE),
                        "is_system": is_system,
                    })
                    continue
            if records:  # continuation of previous message
                records[-1]["text"] += "\n" + line.strip(INVISIBLE)
    out = []
    for r in records:
        r["text"] = r["text"].strip()
        if DELETED.search(r["text"]):
            continue
        r["has_media"] = bool(MEDIA.search(r["text"]))
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", help="WhatsApp export .txt file(s)")
    ap.add_argument("--since", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--until", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--sender", help="filter by sender (substring, case-insensitive)")
    ap.add_argument("--grep", help="regex filter on message text (case-insensitive)")
    ap.add_argument("--no-system", action="store_true", help="drop system messages")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dayfirst", action="store_true", default=True)
    g.add_argument("--monthfirst", action="store_true")
    ap.add_argument("--format", choices=["jsonl", "json", "csv"], default="json")
    ap.add_argument("--stats", action="store_true", help="print summary instead of records")
    ap.add_argument("--out", help="output file (default stdout)")
    a = ap.parse_args()

    recs = []
    for p in a.files:
        for r in parse(p, dayfirst=not a.monthfirst):
            r["source"] = p.rsplit("/", 1)[-1]
            recs.append(r)
    recs.sort(key=lambda r: r["timestamp"])

    if a.since:
        recs = [r for r in recs if r["date"] >= a.since]
    if a.until:
        recs = [r for r in recs if r["date"] <= a.until]
    if a.sender:
        s = a.sender.lower()
        recs = [r for r in recs if s in r["sender"].lower()]
    if a.grep:
        rx = re.compile(a.grep, re.I)
        recs = [r for r in recs if rx.search(r["text"])]
    if a.no_system:
        recs = [r for r in recs if not r["is_system"]]

    out = open(a.out, "w", encoding="utf-8", newline="") if a.out else sys.stdout
    try:
        if a.stats:
            stats = {
                "total_messages": len(recs),
                "range": [recs[0]["timestamp"], recs[-1]["timestamp"]] if recs else None,
                "by_sender": dict(Counter(r["sender"] or "(system)" for r in recs).most_common()),
                "by_date": dict(sorted(Counter(r["date"] for r in recs).items())),
                "media_messages": sum(r["has_media"] for r in recs),
            }
            json.dump(stats, out, ensure_ascii=False, indent=2)
            out.write("\n")
        elif a.format == "jsonl":
            for r in recs:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
        elif a.format == "csv":
            w = csv.DictWriter(out, fieldnames=["timestamp", "date", "time", "sender", "text", "is_system", "has_media", "source"])
            w.writeheader()
            w.writerows(recs)
        else:
            json.dump(recs, out, ensure_ascii=False, indent=2)
            out.write("\n")
    finally:
        if a.out:
            out.close()
    if a.out:
        print(f"{len(recs)} pesan ditulis ke {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
