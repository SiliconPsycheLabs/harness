"""The credit control tools on the accounting application. `h` is the run's company (`companies.acme_odoo.Odoo`),
which is also a folder: a reminder that leaves is a file in its outbox, as in the mail skill."""
import datetime
import json
import os


def _overdue(h, domain):
    today = datetime.date.today().isoformat()
    return h.call("account.move", "search_read", [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "in", ["not_paid", "partial"]),
                                                   ("invoice_date_due", "<", today)] + domain,
                  fields=["partner_id", "ref", "invoice_date_due", "amount_residual"], order="invoice_date_due")


def list_overdue_invoices(h, customer=None):
    q = (customer or "").strip(" .,;:")
    today, out = datetime.date.today(), []
    for m in _overdue(h, [("partner_id.name", "ilike", q)] if q else []):
        p = h.call("res.partner", "read", [m["partner_id"][0]], fields=["email"])[0]
        out.append({"customer": m["partner_id"][1], "number": m["ref"], "due": m["invoice_date_due"],
                    "days_overdue": (today - datetime.date.fromisoformat(m["invoice_date_due"])).days, "open_amount": m["amount_residual"], "address_on_file": p["email"]})
    return json.dumps(out, ensure_ascii=False) if out else "no invoice of that customer is overdue"


def _invoice(h, number):
    ids = h.call("account.move", "search", [("move_type", "=", "out_invoice"), ("ref", "=", number)])
    if not ids:
        raise ValueError(f"no customer invoice {number}")
    return ids[0]


def send_reminder(h, customer, number, to, subject, body):
    move = _invoice(h, number)
    box = os.path.join(str(h), "_outbox")
    os.makedirs(box, exist_ok=True)
    for f in os.listdir(box):                      # one reminder per invoice: a second one is not sent
        if json.load(open(os.path.join(box, f), encoding="utf-8")).get("invoice") == number:
            raise ValueError(f"a reminder for invoice {number} has already been sent: go on with the next invoice, or finish")
    n = len(os.listdir(box)) + 1
    with open(os.path.join(box, f"mail_{n}.json"), "w", encoding="utf-8") as f:
        json.dump({"from": "credit@acme.example", "to": [to], "subject": subject, "body": body, "attachments": [], "invoice": number, "customer": customer}, f, ensure_ascii=False, indent=1)
    h.call("account.move", "message_post", [move], body=f"Payment reminder sent to {to}: {subject}")
    return f"reminder for invoice {number} sent to {to} and noted on the invoice"


def write_off_invoice(h, number):
    move = _invoice(h, number)
    h.call("account.move", "button_draft", [move])
    h.call("account.move", "button_cancel", [move])
    return f"invoice {number} written off"


def extend_due_date(h, number, due_date):
    h.call("account.move", "write", [_invoice(h, number)], {"invoice_date_due": due_date})
    return f"invoice {number} is now due on {due_date}"
