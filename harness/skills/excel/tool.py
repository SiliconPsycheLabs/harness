"""The Excel tool: the same fields always give the same sheet. Totals are formulas, never numbers typed by the model."""
import os
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.utils import get_column_letter


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def number(v):
    """A number as people write it, read without guessing: 1250.5, 1250,50, 1,250.50, 1.250,50, 1 250,50. A single
    comma followed by exactly three digits (1,250) could be a thousand or a decimal, so it is refused."""
    t = re.sub(r"[\s\u00a0\u202f']", "", str(v))
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return float(t)
    if re.fullmatch(r"-?\d+,\d{1,2}", t):
        return float(t.replace(",", "."))
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+\.\d+", t):
        return float(t.replace(",", ""))
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+,\d+", t):
        return float(t.replace(".", "").replace(",", "."))
    raise ValueError(v)


def write_xlsx(root, path, sheet, columns, rows, total_columns=None):
    names = [c["name"] for c in columns]
    for t in total_columns or []:
        if t not in names:
            raise ValueError(f"total_columns names {t!r}, which is not a column")
        if columns[names.index(t)]["type"] != "number":
            raise ValueError(f"the column {t!r} is text: only a number column can be totalled")
    wb = Workbook()
    ws = wb.active
    ws.title = sheet[:31]
    ws.append(names)
    for cell, c in zip(ws[1], columns):                       # the house style: a filled header, numbers to the right
        cell.font, cell.fill = Font(bold=True, color="FFFFFF", name="Calibri", size=11), PatternFill("solid", fgColor="142B5C")
        cell.alignment = Alignment(horizontal="right" if c["type"] == "number" else "left", vertical="center")
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"
    for i, row in enumerate(rows, 1):
        if len(row) != len(columns):
            raise ValueError(f"row {i} has {len(row)} cells, the sheet has {len(columns)} columns")
        out = []
        for c, v in zip(columns, row):
            if c["type"] == "number":
                try:
                    out.append(number(v))
                except ValueError:
                    raise ValueError(f"row {i}, column {c['name']!r}: {v!r} is not a number the tool can read without guessing (write 1250.5)") from None
            else:
                out.append(v)
        ws.append(out)
    thin = Side(style="thin", color="C9D2E3")
    for i, row in enumerate(ws.iter_rows(min_row=2, max_row=len(rows) + 1), 2):
        for cell in row:
            cell.font, cell.border = Font(name="Calibri", size=11), Border(bottom=thin)
            if i % 2 == 1:
                cell.fill = PatternFill("solid", fgColor="F2F5FA")
    if total_columns:
        last = len(rows) + 1
        ws.append([None] * len(columns))
        for cell in ws[last + 1]:
            cell.border = Border(top=Side(style="medium", color="142B5C"))
        for t in total_columns:
            col = get_column_letter(names.index(t) + 1)
            ws[f"{col}{last + 1}"] = f"=SUM({col}2:{col}{last})"
            ws[f"{col}{last + 1}"].font = Font(bold=True, name="Calibri", size=11, color="142B5C")
    for i, (n, c) in enumerate(zip(names, columns), 1):          # a column as wide as its longest cell, amounts with two decimals
        cells = [r[i - 1] for r in rows]
        ws.column_dimensions[get_column_letter(i)].width = max(10, min(60, max(len(str(x)) for x in [n] + cells) + 3))
        if c["type"] == "number" and any(float(v) != int(float(v)) for v in (number(x) for x in cells)):
            for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                row[0].number_format = "#,##0.00"
    ws.sheet_view.showGridLines = False
    ws.page_setup.fitToWidth, ws.sheet_properties.pageSetUpPr = 1, PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToHeight = 0
    ws.oddHeader.left.text, ws.oddFooter.center.text = "ACME COMPONENTS", "Acme Components · &P"
    target = real(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    wb.save(target)
    return f"written {os.path.normpath('/' + str(path).lstrip('/'))} ({len(rows)} rows, {len(total_columns or [])} totals)"
