"""The customer support tools of the job's own: the customers' register, the reply that leaves (a file in the outbox,
as in the mail skill) and the refund proposed for payment (a file in the refunds folder). Fixed programs."""
import json
import os
import sqlite3

from harness.companies.acme_files import CUSTOMER_MAIL


def find_customer(root, name):
    q = name.strip(" .,;:").casefold()
    words = [w for w in q.split() if len(w) > 3]
    got = [{"name": k, "address_on_file": v} for k, v in CUSTOMER_MAIL.items() if q in k.casefold() or (words and all(w in k.casefold() for w in words[:2]))]
    return json.dumps(got, ensure_ascii=False) if got else "no customer in the register matches that name"


def reply_to_customer(root, customer, to, subject, body):
    box = os.path.join(str(root), "_outbox")
    os.makedirs(box, exist_ok=True)
    if os.listdir(box):                             # one reply per message: a second one is not sent
        raise ValueError("the reply to this message has already been sent: finish")
    with open(os.path.join(box, "mail_1.json"), "w", encoding="utf-8") as f:
        json.dump({"from": "support@acme.example", "to": [to], "subject": subject, "body": body, "attachments": [], "customer": customer}, f, ensure_ascii=False, indent=1)
    return f"reply sent to {to}"


def propose_refund(root, customer, order_id, amount, reason=None):
    c = sqlite3.connect(os.path.join(str(root), "_db", "acme.sqlite"))
    try:
        row = c.execute("select c.name from orders o join customers c on c.id = o.customer_id where o.id = ?", (int(order_id),)).fetchone()
    finally:
        c.close()
    if not row:
        raise ValueError(f"no order {order_id}")
    if row[0] != customer:
        raise ValueError(f"order {order_id} is not an order of {customer!r}")
    box = os.path.join(str(root), "_refunds")
    os.makedirs(box, exist_ok=True)
    n = len(os.listdir(box)) + 1
    with open(os.path.join(box, f"refund_{n}.json"), "w", encoding="utf-8") as f:
        json.dump({"customer": customer, "order": int(order_id), "amount": round(float(amount), 2), "reason": reason or ""}, f, ensure_ascii=False, indent=1)
    return f"refund of {float(amount):.2f} EUR for order {int(order_id)} of {customer} approved and recorded for payment"
