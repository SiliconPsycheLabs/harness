"""The PDF tools. Reading gives the text of each page; saving writes the record the same way every time."""
import json
import os

from pypdf import PdfReader


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def read_pdf(root, path):
    full = real(root, path)
    if not os.path.isfile(full):
        raise ValueError(f"no file at {path}")
    os.makedirs(os.path.join(str(root), "_log"), exist_ok=True)
    with open(os.path.join(str(root), "_log", "reads.txt"), "a") as f:      # what was read, for the check
        f.write(os.path.normpath("/" + str(path).lstrip("/")) + "\n")
    pages = PdfReader(full).pages
    return "\n".join(f"--- page {i} of {len(pages)} ---\n{p.extract_text()}" for i, p in enumerate(pages, 1))


def save_record(root, path, supplier, number, date, lines, total, total_page, due_date=None):
    rec = {"supplier": supplier, "number": number, "date": date, "due_date": due_date, "lines": lines, "total": total, "total_page": total_page}
    target = real(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return f"saved {os.path.normpath('/' + str(path).lstrip('/'))} ({len(lines)} lines)"
