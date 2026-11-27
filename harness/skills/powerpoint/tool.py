"""The PowerPoint tool: the same fields always give the same presentation, in the company's style."""
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Inches, Pt

NAVY, INK, ZEBRA, RULE, WHITE = RGBColor(0x14, 0x2B, 0x5C), RGBColor(0x1E, 0x24, 0x30), RGBColor(0xF2, 0xF5, 0xFA), RGBColor(0xC9, 0xD2, 0xE3), RGBColor(0xFF, 0xFF, 0xFF)


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def _box(slide, x, y, w, h, fill):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    return s


def _text(slide, x, y, w, h, text, size, color, bold=False):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    run = tf.paragraphs[0].add_run()
    run.text = text
    run.font.size, run.font.bold, run.font.color.rgb, run.font.name = Pt(size), bold, color, "Calibri"
    return tf


def write_pptx(root, path, title, slides, subtitle=None):
    slides = [dict(s) for s in slides]
    for n, s in enumerate(slides, 1):
        if s.get("table_header") or s.get("table_rows"):          # a table as lines: "a | b | c"
            if not (s.get("table_header") and s.get("table_rows")):
                raise ValueError(f"slide {n} ({s['title']!r}): a table needs both table_header and table_rows")
            s["table"] = {"columns": [c.strip() for c in s["table_header"].split("|")], "rows": [[c.strip() for c in row.split("|")] for row in s["table_rows"]]}
        if not s.get("bullets") and not s.get("table"):
            raise ValueError(f"slide {n} ({s['title']!r}) has neither bullets nor a table")
        if s.get("table"):
            width = len(s["table"]["columns"])
            for i, row in enumerate(s["table"]["rows"], 1):
                if len(row) != width:
                    raise ValueError(f"slide {n}: row {i} of the table has {len(row)} cells, the table has {width} columns")
    p = Presentation()
    p.slide_width, p.slide_height = Inches(13.333), Inches(7.5)
    W, H = p.slide_width, p.slide_height
    blank = p.slide_layouts[6]
    first = p.slides.add_slide(blank)                                   # the title slide: a navy page
    _box(first, 0, 0, W, H, NAVY)
    _text(first, Inches(0.9), Inches(0.6), Inches(8), Inches(0.5), "ACME COMPONENTS", 14, RULE, True)
    _text(first, Inches(0.9), Inches(2.6), Inches(11.5), Inches(1.8), title, 44, WHITE, True)
    if subtitle:
        _text(first, Inches(0.9), Inches(4.6), Inches(11.5), Inches(0.8), subtitle, 20, RULE)
    for n, s in enumerate(slides, 2):
        sl = p.slides.add_slide(blank)
        _box(sl, 0, 0, W, Inches(1.25), NAVY)
        _text(sl, Inches(0.7), Inches(0.3), Inches(12), Inches(0.8), s["title"], 30, WHITE, True)
        top = Inches(1.7)
        if s.get("bullets"):
            tf = _text(sl, Inches(0.9), top, Inches(11.5), Inches(0.5 * len(s["bullets"]) + 0.4), "", 22, INK)
            for i, b in enumerate(s["bullets"]):
                par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                run = par.add_run()
                run.text = "•  " + b
                run.font.size, run.font.color.rgb, run.font.name = Pt(22), INK, "Calibri"
                par.space_after = Pt(10)
            top = Emu(top + Inches(0.62 * len(s["bullets"]) + 0.3))
        if s.get("table"):
            cols, rows = s["table"]["columns"], s["table"]["rows"]
            shape = sl.shapes.add_table(len(rows) + 1, len(cols), Inches(0.9), top, Inches(11.5), Inches(0.5 * (len(rows) + 1)))
            for j, c in enumerate(cols):
                cell = shape.table.cell(0, j)
                cell.text = c
                cell.fill.solid()
                cell.fill.fore_color.rgb = NAVY
                f = cell.text_frame.paragraphs[0].runs[0].font
                f.bold, f.size, f.color.rgb, f.name = True, Pt(16), WHITE, "Calibri"
            for i, row in enumerate(rows, 1):
                for j, v in enumerate(row):
                    cell = shape.table.cell(i, j)
                    cell.text = str(v)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = ZEBRA if i % 2 == 0 else WHITE
                    f = cell.text_frame.paragraphs[0].runs[0].font if cell.text_frame.paragraphs[0].runs else None
                    if f:
                        f.size, f.color.rgb, f.name = Pt(16), INK, "Calibri"
        _box(sl, Inches(0.7), Inches(6.95), Inches(11.93), Emu(9525), RULE)
        _text(sl, Inches(0.7), Inches(7.0), Inches(8), Inches(0.4), "Acme Components", 11, NAVY)
        _text(sl, Inches(12.2), Inches(7.0), Inches(0.6), Inches(0.4), str(n), 11, NAVY)
    target = real(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    p.save(target)
    names = "; ".join(s["title"] for s in slides)
    return (f"written {os.path.normpath('/' + str(path).lstrip('/'))}: the title slide and {len(slides)} slide(s) ({names}). "
            "The file holds exactly these slides: if the colleague asked for more, call again with all of them.")
