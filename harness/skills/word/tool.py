"""The Word tool: the same fields always give the same file, in the company's house style (letterhead, type, tables).
The look is the program's, not the model's: every document comes out the same way whatever model filled the fields.
`root` is the company's file tree for this run; the path the model names is a path of the company
(`/acme/documents/x.docx`) and is written under `root`."""
import os
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor

ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "right": WD_ALIGN_PARAGRAPH.RIGHT, "center": WD_ALIGN_PARAGRAPH.CENTER,
         "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}
FONT, INK, NAVY, GREY = "Calibri", RGBColor(0x1E, 0x24, 0x30), RGBColor(0x14, 0x2B, 0x5C), RGBColor(0x6A, 0x73, 0x82)
BAND, ZEBRA, RULE = "142B5C", "F2F5FA", "C9D2E3"
NUMBER = re.compile(r"^[\s€$]*-?\d[\d.,'\u00a0 ]*(\s?(%|EUR|euro|euros|Euro|€))?$")


def real(root, path):
    """The file on disk for a path of the company: normalised as text, always inside `root`."""
    p = os.path.normpath("/" + str(path))
    return os.path.join(str(root), p.lstrip("/"))


def _font(style, size, bold=False, color=INK):
    style.font.name = FONT
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    style.font.size, style.font.bold, style.font.color.rgb = Pt(size), bold, color


def _border(paragraph, side, color, size=8, space=6):
    pPr = paragraph._p.get_or_add_pPr()
    for old in pPr.findall(qn("w:pBdr")):
        pPr.remove(old)
    pPr.append(parse_xml(f'<w:pBdr {nsdecls("w")}><w:{side} w:val="single" w:sz="{size}" w:space="{space}" w:color="{color}"/></w:pBdr>'))


def _page_number(paragraph):
    run = paragraph.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)


def house_style(doc):
    sec = doc.sections[0]
    sec.top_margin, sec.bottom_margin, sec.left_margin, sec.right_margin = Cm(2.4), Cm(2.2), Cm(2.4), Cm(2.4)
    st = doc.styles
    _font(st["Normal"], 11)
    st["Normal"].paragraph_format.space_after, st["Normal"].paragraph_format.line_spacing = Pt(7), 1.2
    _font(st["Title"], 24, True, NAVY)
    st["Title"].paragraph_format.space_before, st["Title"].paragraph_format.space_after = Pt(6), Pt(16)
    for name, size in (("Heading 1", 15), ("Heading 2", 13), ("Heading 3", 11.5)):
        _font(st[name], size, True, NAVY)
        st[name].paragraph_format.space_before, st[name].paragraph_format.space_after = Pt(16), Pt(5)
    for name in ("List Bullet", "List Number"):
        _font(st[name], 11)
        st[name].paragraph_format.space_after = Pt(3)
    head = sec.header.paragraphs[0]
    r = head.add_run("ACME COMPONENTS")
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(10), True, NAVY
    r._r.get_or_add_rPr().append(parse_xml(f'<w:spacing {nsdecls("w")} w:val="40"/>'))
    r2 = head.add_run("    machine parts since 1987")
    r2.font.name, r2.font.size, r2.font.color.rgb = FONT, Pt(8.5), GREY
    _border(head, "bottom", "1F5AD6", 10, 6)
    foot = sec.footer.paragraphs[0]
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r3 = foot.add_run("Acme Components   ·   office@acme.example   ·   ")
    r3.font.name, r3.font.size, r3.font.color.rgb = FONT, Pt(8), GREY
    _page_number(foot)
    for run in foot.runs:
        run.font.size, run.font.color.rgb = Pt(8), GREY


def _table(doc, rows):
    cols = max(len(r) for r in rows)
    t = doc.add_table(rows=len(rows), cols=cols)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t._tbl.tblPr.append(parse_xml(
        f'<w:tblBorders {nsdecls("w")}><w:top w:val="single" w:sz="6" w:color="{BAND}"/><w:bottom w:val="single" w:sz="6" w:color="{BAND}"/>'
        f'<w:insideH w:val="single" w:sz="4" w:color="{RULE}"/></w:tblBorders>'))
    t._tbl.tblPr.append(parse_xml(f'<w:tblCellMar {nsdecls("w")}><w:top w:w="70" w:type="dxa"/><w:bottom w:w="70" w:type="dxa"/>'
                                  f'<w:left w:w="110" w:type="dxa"/><w:right w:w="110" w:type="dxa"/></w:tblCellMar>'))
    for i, r in enumerate(rows):
        for j in range(cols):
            cell = t.cell(i, j)
            text = r[j] if j < len(r) else ""
            cell.text = text
            par = cell.paragraphs[0]
            par.paragraph_format.space_after = Pt(0)
            fill = BAND if i == 0 else (ZEBRA if i % 2 == 0 else None)
            if fill:
                cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{fill}"/>'))
            if j > 0 and (NUMBER.match(text or "") or (i == 0 and all(NUMBER.match(x[j] or "") for x in rows[1:] if j < len(x)))):
                par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for run in par.runs:
                run.font.name, run.font.size = FONT, Pt(10.5)
                if i == 0:
                    run.font.bold, run.font.color.rgb = True, RGBColor(0xFF, 0xFF, 0xFF)
    doc.add_paragraph("").paragraph_format.space_after = Pt(2)


def write_docx(root, path, title, blocks):
    doc = Document()
    house_style(doc)
    doc.core_properties.title = title
    head = doc.add_heading(title, level=0)
    _border(head, "bottom", RULE, 6, 8)
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
            _table(doc, rows)
        elif kind == "signature":
            lines = b.get("items") or (b["text"].split("\n") if b.get("text") else [])
            doc.add_paragraph("").paragraph_format.space_after = Pt(10)
            for k, line in enumerate(lines):
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(1)
                if k == 0 and p.runs:
                    p.runs[0].font.bold = True
        else:
            raise ValueError(f"unknown block type {kind!r}")
    target = real(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    doc.save(target)
    return f"written {os.path.normpath('/' + str(path).lstrip('/'))} ({len(blocks)} blocks)"
