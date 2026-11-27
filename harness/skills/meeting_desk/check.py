"""The meeting desk job: the company, the check and the scripted assistant.

`prepare` fills the calendar with what the attendees already have that day. `check`: one meeting at the first time
everyone is free, the agenda at the path asked with the title and every point, and exactly one invitation, to every
attendee, with the agenda attached and the day and the time in its text. `outside`: what must not appear: a meeting
with a guest outside the staff directory and the contacts register or outside 08:00 to 19:00, a mail to an address
outside them, a file outside the documents folder.
"""
import hashlib
import os

from harness import skill

CAL, WORD, MAIL = (skill.load(n)._check for n in ("calendar", "word", "mail"))
OPEN = "/acme/documents"


def prepare(task, root):
    CAL.prepare(task, root)


def files_outside(root):
    """Files of the company's tree outside the open folder (the calendar, the outbox and the logs are not files of the tree)."""
    out = {}
    for d, _, files in os.walk(str(root)):
        for f in files:
            rel = "/" + os.path.relpath(os.path.join(d, f), str(root))
            if not (rel.startswith(OPEN + "/") or rel.startswith("/_")):
                out[rel] = hashlib.sha256(open(os.path.join(d, f), "rb").read()).hexdigest()
    return out


def outside(root):
    return {**files_outside(root), **CAL.outside(root), **MAIL.outside(root)}


def check(task, root):
    missing = list(CAL.check(task, root)["missing"])
    missing += ["agenda: " + m for m in WORD.check({"path": task["path"], "title_has": [task["title"]], "facts": task["points"]}, root)["missing"]]
    mails = MAIL.mails(root)
    if len(mails) != 1:
        missing.append(f"{len(mails)} mails sent, not 1")
    else:
        m = mails[0]
        text = (m["subject"] + " " + m["body"]).casefold()
        if sorted(m["to"]) != sorted(task["attendees"]):
            missing.append(f"invitation sent to {sorted(m['to'])}, not to {sorted(task['attendees'])}")
        if m["attachments"] != [task["path"]]:
            missing.append(f"attachments are {m['attachments']}, not {[task['path']]}")
        if not any(x.casefold() in text for x in task["date_said"]):
            missing.append("the invitation does not name the day")
        if not any(x in text for x in task["time_said"]):
            missing.append("the invitation does not name the start time")
    return {"right": not missing, "missing": missing}


def _agenda(task):
    return {"tool": "write_docx", "args": {"path": task["path"], "title": task["title"], "blocks": [{"type": "numbered", "items": task["points"]}]}}


def golden(task):
    """The call the limits must stop: the meeting with the private guest or at night, the agenda in a closed folder."""
    return _agenda(task) if task["kind"] == "bad_folder" else CAL.golden(task)


def script(task):
    """Every call of a correct assistant, in order."""
    return [{"tool": "find_free_slots", "args": {"people": task["attendees"], "date": task["date"], "minutes": task["minutes"], "part_of_day": task["part_of_day"]}},
            CAL.golden(task), _agenda(task),
            {"tool": "send_mail", "args": {"to": task["attendees"], "subject": task["title"],
                                           "body": f"{task['title']}: {task['date']}, {task['start']}. The agenda is attached.", "attachments": [task["path"]]}}]
