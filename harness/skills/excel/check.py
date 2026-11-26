"""Reads a written sheet against what its request asked: every row with its numbers as numbers, each total a formula
over the right column. `golden(task)` is the call a correct agent would make."""
import hashlib
import os

from openpyxl import load_workbook

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


def check(task, root):
    path = real(root, task["path"])
    if not os.path.isfile(path):
        return {"right": False, "missing": ["no file at the path asked"]}
    try:
        ws = load_workbook(path).active
    except Exception as x:  # noqa: BLE001
        return {"right": False, "missing": [f"the file does not open as an Excel sheet: {type(x).__name__}"]}
    grid = [[c.value for c in row] for row in ws.iter_rows()]
    t, missing = task["table"], []
    data = [r for r in grid[1:] if any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in r)]
    if len(grid[0]) != len(t["columns"]):
        missing.append(f"{len(grid[0])} columns, not {len(t['columns'])}")
    if len(data) != len(t["rows"]):
        missing.append(f"{len(data)} rows of data, not {len(t['rows'])}")
    for want in t["rows"]:
        nums = [float(v) for c, v in zip(t["columns"], want) if c["type"] == "number"]
        label = str(want[0]).casefold()
        if not any(label in " ".join(str(v) for v in r if isinstance(v, str)).casefold()
                   and all(any(isinstance(v, (int, float)) and abs(v - n) < 0.005 for v in r) for n in nums) for r in data):
            missing.append(f"no row {want[0]} with its numbers")
    names = [c["name"] for c in t["columns"]]
    for col in t.get("total_columns", []):
        j = names.index(col)
        formula = next((r[j] for r in grid[1:] if j < len(r) and isinstance(r[j], str) and r[j].upper().startswith("=SUM(")), None)
        added = round(sum(r[j] for r in data if j < len(r) and isinstance(r[j], (int, float))), 2)
        want = round(sum(float(r[j]) for r in t["rows"]), 2)
        if formula is None:
            missing.append(f"no SUM formula under {col}")
        elif abs(added - want) > 0.01:
            missing.append(f"{col} adds up to {added:.2f}, not {want:.2f}")
    return {"right": not missing, "missing": missing}


def golden(task):
    t = task.get("table") or {"columns": [{"name": "A", "type": "text"}], "rows": [["x"]]}
    return {"tool": "write_xlsx", "args": {"path": task["path"], "sheet": task.get("sheet", "Sheet"), "columns": t["columns"],
                                           "rows": [[str(v) for v in r] for r in t["rows"]], "total_columns": t.get("total_columns", [])}}
