"""The accounts-payable tools on the accounting application. `h` is the run's company (`companies.acme_odoo.Odoo`).
Each tool does one thing through the application's own interface, the same way every time."""
import json


def _supplier(h, name):
    got = h.call("res.partner", "search_read", [("name", "=", name), ("is_company", "=", True)], fields=["name"], limit=1)
    if not got:
        raise ValueError(f"no supplier named {name!r} in the register")
    return got[0]["id"]


LEGAL = {"ltd", "ltd.", "inc", "inc.", "gmbh", "ag", "sarl", "s.r.l.", "srl", "s.p.a.", "spa", "s.l.", "sl", "s.a.", "sa", "co", "co.", "llc"}


def _lookups(name):
    """The name as written, then without the punctuation at its ends, then without its legal form: what a person
    typing in the register's search box would try."""
    tried = []
    for q in (name, name.strip(" .,;:"), " ".join(w for w in name.strip(" .,;:").split() if w.casefold() not in LEGAL)):
        if q and q not in tried:
            tried.append(q)
    return tried


def find_supplier(h, name):
    got = []
    for q in _lookups(name):
        got = h.call("res.partner", "search_read", [("name", "ilike", q), ("is_company", "=", True), ("supplier_rank", ">", 0)],
                     fields=["name", "country_id", "bank_ids"], limit=10)
        if got:
            break
    out = []
    for p in got:
        banks = h.call("res.partner.bank", "read", p["bank_ids"], fields=["acc_number"]) if p["bank_ids"] else []
        out.append({"name": p["name"], "country": (p["country_id"] or [0, ""])[1], "bank_account": [b["acc_number"] for b in banks]})
    return json.dumps(out, ensure_ascii=False) if out else "no supplier in the register matches"


def create_supplier_bill(h, supplier, number, date, lines, total, due_date=None):
    pid = _supplier(h, supplier)
    for n, x in enumerate(lines, 1):
        if float(x["quantity"]) <= 0:
            raise ValueError(f"line {n} has quantity {x['quantity']}: enter only the lines the invoice has, each with its quantity")
    added = round(sum(float(x["quantity"]) * float(x["unit_price"]) for x in lines), 2)
    if abs(added - float(total)) > 0.01:
        raise ValueError(f"the lines add up to {added:.2f}, not to the total {float(total):.2f}")
    if h.call("account.move", "search", [("move_type", "=", "in_invoice"), ("partner_id", "=", pid), ("ref", "=", number)]):
        raise ValueError(f"invoice {number} of {supplier} is already entered")
    vals = {"move_type": "in_invoice", "partner_id": pid, "ref": number, "invoice_date": date,
            "invoice_line_ids": [(0, 0, {"name": x["description"], "quantity": float(x["quantity"]),
                                          "price_unit": float(x["unit_price"]), "tax_ids": [(6, 0, [])]}) for x in lines]}
    if due_date:
        vals["invoice_date_due"] = due_date
    move = h.call("account.move", "create", vals)
    return f"entered as draft bill {move}: {supplier}, invoice {number}, net total {added:.2f} EUR, waiting for validation"


def create_supplier(h, name, iban=None):
    pid = h.call("res.partner", "create", {"name": name, "is_company": True, "supplier_rank": 1})
    if iban:
        h.call("res.partner.bank", "create", {"partner_id": pid, "acc_number": iban})
    return f"supplier {name} added to the register"


def set_supplier_bank(h, supplier, iban):
    pid = _supplier(h, supplier)
    old = h.call("res.partner.bank", "search", [("partner_id", "=", pid)])
    if old:
        h.call("res.partner.bank", "unlink", old)
    h.call("res.partner.bank", "create", {"partner_id": pid, "acc_number": iban})
    return f"bank account of {supplier} is now {iban}"
