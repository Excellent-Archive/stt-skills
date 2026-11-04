#!/usr/bin/env python3
"""Fill {{placeholder}} fields in a report template (.docx, .md, .txt).

  List fields : fill_template.py --list template.docx
  Fill        : fill_template.py template.docx --data data.json --out result.docx

Missing fields become "[PERLU KONFIRMASI: field]" and are reported on stderr.
List values are written as bullet lines.
"""
import argparse
import json
import re
import sys

PH = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")


def render(value):
    if isinstance(value, list):
        return "\n".join(f"• {v}" for v in value)
    if isinstance(value, dict):
        return "\n".join(f"{k}: {v}" for k, v in value.items())
    return "" if value is None else str(value)


def substitute(text, data, missing):
    def rep(m):
        key = m.group(1)
        if key in data:
            return render(data[key])
        missing.add(key)
        return f"[PERLU KONFIRMASI: {key}]"
    return PH.sub(rep, text)


def iter_docx_paragraphs(doc):
    def from_container(c):
        for p in c.paragraphs:
            yield p
        for t in getattr(c, "tables", []):
            for row in t.rows:
                for cell in row.cells:
                    yield from from_container(cell)
    yield from from_container(doc)
    for s in doc.sections:
        for part in (s.header, s.footer, s.first_page_header, s.first_page_footer):
            try:
                yield from from_container(part)
            except Exception:
                pass


def docx_fields(path):
    from docx import Document
    doc = Document(path)
    found = []
    for p in iter_docx_paragraphs(doc):
        for k in PH.findall(p.text):
            if k not in found:
                found.append(k)
    return found


def fill_docx(path, data, out):
    from docx import Document
    doc = Document(path)
    missing = set()
    seen = set()
    for p in iter_docx_paragraphs(doc):
        if id(p._p) in seen or "{{" not in p.text:
            continue
        seen.add(id(p._p))
        new = substitute(p.text, data, missing)
        runs = p.runs
        if not runs:
            continue
        # keep formatting of the first run; placeholders often split across runs
        runs[0].text = new
        for r in runs[1:]:
            r.text = ""
    doc.save(out)
    return missing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template")
    ap.add_argument("--list", action="store_true", help="list placeholders and exit")
    ap.add_argument("--data", help="JSON file with field values")
    ap.add_argument("--out", help="output path")
    a = ap.parse_args()

    is_docx = a.template.lower().endswith(".docx")

    if a.list:
        if is_docx:
            fields = docx_fields(a.template)
        else:
            text = open(a.template, encoding="utf-8").read()
            fields = list(dict.fromkeys(PH.findall(text)))
        print(json.dumps(fields, ensure_ascii=False, indent=2))
        return

    if not a.data or not a.out:
        ap.error("--data dan --out wajib diisi untuk mengisi template")
    data = json.load(open(a.data, encoding="utf-8"))

    if is_docx:
        missing = fill_docx(a.template, data, a.out)
    else:
        missing = set()
        text = open(a.template, encoding="utf-8").read()
        open(a.out, "w", encoding="utf-8").write(substitute(text, data, missing))

    print(f"Dokumen ditulis ke {a.out}", file=sys.stderr)
    if missing:
        print("Field PERLU KONFIRMASI: " + ", ".join(sorted(missing)), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
