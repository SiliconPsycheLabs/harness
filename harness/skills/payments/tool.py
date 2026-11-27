"""The payment tools on the accounting application. `h` is the run's company (`companies.acme_odoo.Odoo`)."""
import json


def _bills(h, domain):
    return h.call("account.move", "search_read", [("move_type", "=", "in_invoice"), ("state", "=", "posted"),
                                                   ("payment_state", "in", ["not_paid", "partial"])] + domain,
                  fields=["partner_id", "ref", "invoice_date_due", "amount_residual"], order="invoice_date_due")


def _banks(h, partner_id):
    return [b["acc_number"] for b in h.call("res.partner.bank", "search_read", [("partner_id", "=", partner_id)], fields=["acc_number"])]


def list_open_bills(h, supplier=None):
    q = (supplier or "").strip(" .,;:")
    out = [{"supplier": m["partner_id"][1], "number": m["ref"], "due": m["invoice_date_due"], "open_amount": m["amount_residual"],
            "bank_account_on_file": _banks(h, m["partner_id"][0])} for m in _bills(h, [("partner_id.name", "ilike", q)] if q else [])]
    return json.dumps(out, ensure_ascii=False) if out else "no validated bill waits for payment"


def pay_bill(h, supplier, number, amount, iban):
    got = _bills(h, [("partner_id.name", "=", supplier), ("ref", "=", number)])
    if not got:
        raise ValueError(f"no validated, unpaid bill {number} of {supplier!r}")
    m = got[0]
    if abs(m["amount_residual"] - float(amount)) > 0.01:
        raise ValueError(f"the open amount of {number} is {m['amount_residual']:.2f}, not {float(amount):.2f}")
    pid = m["partner_id"][0]
    bank = h.call("res.partner.bank", "search", [("partner_id", "=", pid), ("acc_number", "=", iban)])
    bank_id = bank[0] if bank else h.call("res.partner.bank", "create", {"partner_id": pid, "acc_number": iban})
    ctx = {"active_model": "account.move", "active_ids": [m["id"]]}
    wiz = h.call("account.payment.register", "create", {"partner_bank_id": bank_id}, context=ctx)
    h.call("account.payment.register", "action_create_payments", [wiz], context=ctx)
    return f"paid {float(amount):.2f} EUR for invoice {number} of {supplier} to {iban}"
