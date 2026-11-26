"""The mail tools. The mail system of the test company is an outbox folder: one file per mail that left."""
import json
import os

from harness.companies.acme_files import CONTACTS


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def find_contact(root, name):
    q = name.strip(" .,;:").casefold()
    got = [{"name": k, "mail": v} for k, v in CONTACTS.items() if q in k.casefold() or any(w in k.casefold() for w in q.split()[:2] if len(w) > 3)]
    return json.dumps(got, ensure_ascii=False) if got else "no company in the contacts register matches"


def send_mail(root, to, subject, body, attachments=None):
    for p in attachments or []:
        if not os.path.isfile(real(root, p)):
            raise ValueError(f"no file to attach at {p}")
    box = os.path.join(str(root), "_outbox")
    os.makedirs(box, exist_ok=True)
    n = len(os.listdir(box)) + 1
    with open(os.path.join(box, f"mail_{n}.json"), "w", encoding="utf-8") as f:
        json.dump({"from": "office@acme.example", "to": to, "subject": subject, "body": body,
                   "attachments": [os.path.normpath("/" + str(p).lstrip("/")) for p in attachments or []]}, f, ensure_ascii=False, indent=1)
    return f"sent to {', '.join(to)} with {len(attachments or [])} attachment(s)"
