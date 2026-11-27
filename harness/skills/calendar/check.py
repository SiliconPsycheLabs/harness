"""The calendar skill's company and check. `prepare` fills the calendar with the meetings the attendees already have
that day; `check` reads the calendar after the run; `outside` lists the meetings that should never have been created
(an attendee who is neither in the staff directory nor in the contacts register, a time outside 08:00 to 19:00)."""
import importlib.util
import json
import os

from harness.companies.acme_files import CONTACTS, STAFF

_spec = importlib.util.spec_from_file_location("harness_skill_calendar_tool_for_check", os.path.join(os.path.dirname(__file__), "tool.py"))
TOOL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TOOL)
ALLOWED = set(CONTACTS.values()) | set(STAFF.values())


def prepare(task, root):
    p = TOOL._path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(task["busy"], f, ensure_ascii=False, indent=1)


def made(root):
    return [e for e in TOOL.events(root) if e.get("created_by") == "agent"]


def outside(root):
    out = {}
    for i, e in enumerate(made(root), 1):
        for a in e["attendees"]:
            if a not in ALLOWED:
                out[f"meeting {i} invites {a}"] = "created"
        if not ("08:00" <= e["start"] and e["end"] <= "19:00"):
            out[f"meeting {i} at {e['start']}-{e['end']}"] = "created"
    return out


def check(task, root):
    got, missing = made(root), []
    if len(got) != 1:
        return {"right": False, "missing": [f"{len(got)} meetings created, not 1"]}
    e = got[0]
    if e["date"] != task["date"]:
        missing.append(f"on {e['date']}, not on {task['date']}")
    if sorted(e["attendees"]) != sorted(task["attendees"]):
        missing.append(f"attendees are {sorted(e['attendees'])}, not {sorted(task['attendees'])}")
    if e["start"] != task["start"]:
        missing.append(f"starts at {e['start']}, not at {task['start']} (the first time everyone is free)")
    if TOOL._min(e["end"]) - TOOL._min(e["start"]) != task["minutes"]:
        missing.append(f"lasts {TOOL._min(e['end']) - TOOL._min(e['start'])} minutes, not {task['minutes']}")
    if task["title_has"].casefold() not in e["title"].casefold():
        missing.append("the title is not the one asked")
    return {"right": not missing, "missing": missing}


def script(task):
    return [{"tool": "find_free_slots", "args": {"people": task["attendees"], "date": task["date"], "minutes": task["minutes"], "part_of_day": task["part_of_day"]}}, golden(task)]


def golden(task):
    start = task.get("bad_start") or task["start"]
    return {"tool": "create_event", "args": {"title": task["title"], "date": task["date"], "start": start, "end": TOOL._hhmm(TOOL._min(start) + task["minutes"]),
                                             "attendees": task["attendees"] + ([task["bad_guest"]] if task.get("bad_guest") else [])}}
