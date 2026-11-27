"""The calendar tools. The company calendar of the test company is one file, `_calendar/events.json`: a list of
events, each with its date, start, end and attendees. Like a real calendar, it accepts a meeting over another one."""
import json
import os

from harness.companies.acme_files import CONTACTS, STAFF


def _path(root):
    return os.path.join(str(root), "_calendar", "events.json")


def events(root):
    return json.load(open(_path(root), encoding="utf-8")) if os.path.isfile(_path(root)) else []


def _min(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def free_starts(evs, people, date, minutes):
    busy = [(_min(e["start"]), _min(e["end"])) for e in evs if e["date"] == date and set(e["attendees"]) & set(people)]
    return [_hhmm(s) for s in range(9 * 60, 18 * 60 - minutes + 1, 30) if all(s + minutes <= a or s >= b for a, b in busy)]


def part(starts, minutes, part_of_day):
    if part_of_day == "morning":
        return [s for s in starts if _min(s) + minutes <= 13 * 60]
    return [s for s in starts if s >= "14:00"] if part_of_day == "afternoon" else starts


def find_person(root, name):
    q = name.strip(" .,;:").casefold()
    words = [w for w in q.split() if len(w) > 2]
    got = [{"name": k, "address": v} for k, v in list(STAFF.items()) + list(CONTACTS.items()) if q in k.casefold() or (words and all(w in k.casefold() for w in words))]
    return json.dumps(got, ensure_ascii=False) if got else "nobody in the staff directory or in the contacts register matches that name"


def find_free_slots(root, people, date, minutes, part_of_day="any"):
    minutes = int(minutes)
    got = part(free_starts(events(root), people, date, minutes), minutes, part_of_day)
    if not got:
        return f"nobody is free together for {minutes} minutes on {date} ({part_of_day})"
    return json.dumps({"date": date, "free_times_in_order": [{"start": s, "end": _hhmm(_min(s) + minutes)} for s in got]})


def create_event(root, title, date, start, end, attendees, location=None):
    evs = events(root)
    evs.append({"title": title, "date": date, "start": start, "end": end, "attendees": attendees, "location": location or "", "created_by": "agent"})
    os.makedirs(os.path.dirname(_path(root)), exist_ok=True)
    with open(_path(root), "w", encoding="utf-8") as f:
        json.dump(evs, f, ensure_ascii=False, indent=1)
    return f"created: {title}, {date} {start}-{end}, {len(attendees)} attendee(s) invited"
