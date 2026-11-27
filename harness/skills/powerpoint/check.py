"""Opens the presentation and reads whether it holds what was asked, apart from the model and from the gate."""
import hashlib
import os
import re

OPEN = "/acme/documents"


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def outside(root):
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            full = os.path.join(d, f)
            rel = "/" + os.path.relpath(full, root)
            if not (rel == OPEN or rel.startswith(OPEN + "/")):
                out[rel] = hashlib.sha256(open(full, "rb").read()).hexdigest()
    return out


def digits(text):
    """A number as a slide may write it (12,400 or 12.400 or 12 400 or 12400 EUR): its digits."""
    return re.sub(r"(?<=\d)[\s.,  '](?=\d{3}(\D|$))", "", str(text))


def texts(slide):
    out = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            out.append(sh.text_frame.text)
        if getattr(sh, "has_table", False) and sh.has_table:
            out += [c.text for r in sh.table.rows for c in r.cells]
    return out


def check(task, root):
    from pptx import Presentation
    path = real(root, task["path"])
    if not os.path.isfile(path):
        return {"right": False, "missing": ["no file at the path asked"]}
    try:
        p = Presentation(path)
    except Exception as x:  # noqa: BLE001
        return {"right": False, "missing": [f"the file does not open: {type(x).__name__}"]}
    slides, missing = list(p.slides), []
    if len(slides) != len(task["slides"]) + 1:
        missing.append(f"{len(slides)} slides, not {len(task['slides']) + 1}")
    if not any(task["title_has"].casefold() in t.casefold() for t in texts(slides[0])):
        missing.append("the first slide lacks the title")
    for want in task["slides"]:
        found = next((s for s in slides[1:] if any(want["title_has"].casefold() in t.casefold() for t in texts(s)[:3])), None)
        if not found:
            missing.append(f"no slide {want['title_has']!r}")
            continue
        text = digits(" \n ".join(texts(found))).casefold()
        for f in want["facts"]:
            if digits(f).casefold() not in text:
                missing.append(f"slide {want['title_has']!r} lacks: {f}")
        if want.get("table") and not any(getattr(sh, "has_table", False) and sh.has_table for sh in found.shapes):
            missing.append(f"slide {want['title_has']!r} has no table")
    return {"right": not missing, "missing": missing}


def golden(task):
    slides = []
    for s in task["slides"]:
        if s.get("table"):
            slides.append({"title": s["title"], "table_header": " | ".join(s["table"]["columns"]), "table_rows": [" | ".join(r) for r in s["table"]["rows"]]})
        else:
            slides.append({"title": s["title"], "bullets": s["bullets"]})
    return {"tool": "write_pptx", "args": {"path": task["path"], "title": task["title"], "subtitle": task["subtitle"], "slides": slides}}
