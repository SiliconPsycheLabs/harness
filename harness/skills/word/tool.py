"""The Word tool: the same fields always give the same file. `root` is the company's file tree for this run; the
path the model names is a path of the company (`/acme/documents/x.docx`) and is written under `root`."""
import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "right": WD_ALIGN_PARAGRAPH.RIGHT, "center": WD_ALIGN_PARAGRAPH.CENTER,
         "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}


def real(root, path):
    """The file on disk for a path of the company: normalised as text, always inside `root`."""
    p = os.path.normpath("/" + str(path))
    return os.path.join(str(root), p.lstrip("/"))


def write_docx(root, path, title, blocks):
    doc = Document()
    doc.core_properties.title = title
    doc.add_heading(title, level=0)
    for b in blocks:
        kind = b.get("type")
        if kind == "heading":
            doc.add_heading(b.get("text", ""), level=int(b.get("level", 1)))
        elif kind == "paragraph":
            p = doc.add_paragraph(b.get("text", ""))
            if b.get("align"):
                p.alignment = ALIGN[b["align"]]
        elif kind in ("bullets", "numbered"):
            style = "List Bullet" if kind == "bullets" else "List Number"
            # A list block may carry its items in `items`, or one item in `text` (smaller models write one block per
            # item): both are written as list items. A list block with neither is refused, never dropped in silence.
            items = b.get("items") or ([b["text"]] if b.get("text") else [])
            if not items:
                raise ValueError(f"a {kind} block needs `items` (one string per item)")
            for item in items:
                doc.add_paragraph(item, style=style)
        elif kind == "table":
            rows = [r for r in (b.get("rows") or []) if r]
            if not rows:
                raise ValueError("a table needs at least one row")
            cols = max(len(r) for r in rows)
            t = doc.add_table(rows=len(rows), cols=cols)
            t.style = "Table Grid"
            for i, r in enumerate(rows):
                for j in range(cols):
                    cell = t.cell(i, j)
                    cell.text = r[j] if j < len(r) else ""
                    if i == 0:
                        for run in cell.paragraphs[0].runs:
                            run.bold = True
        elif kind == "signature":
            doc.add_paragraph("")
            for line in b.get("items") or (b["text"].split("\n") if b.get("text") else []):
                doc.add_paragraph(line)
        else:
            raise ValueError(f"unknown block type {kind!r}")
    target = real(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    doc.save(target)
    return f"written {os.path.normpath('/' + str(path).lstrip('/'))} ({len(blocks)} blocks)"
