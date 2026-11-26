# The invented company and its supplier register. Run inside `odoo-bin shell -d acme`.
SUPPLIERS = [
    ("Northwind Bearings Ltd", "GB", "GB29NWBK60161331926819"),
    ("Tessitura Bellomo S.p.A.", "IT", "IT60X0542811101000000123456"),
    ("Atelier Dumont SARL", "FR", "FR1420041010050500013M02606"),
    ("Suministros Ibarra S.L.", "ES", "ES9121000418450200051332"),
    ("Krämer Werkzeugbau GmbH", "DE", "DE89370400440532013000"),
    ("Officine Galli S.r.l.", "IT", "IT40S0542811101000000654321"),
    ("Lindner Maschinenbau AG", "DE", "DE75512108001245126199"),
    ("Harbor Tools Inc.", "US", "US-ACH-021000021-000123456789"),
]
company = env.company
company.name = "Acme Components"
company.partner_id.name = "Acme Components"
eur = env.ref("base.EUR")
eur.active = True
if company.currency_id != eur:
    company.currency_id = eur
for name, cc, iban in SUPPLIERS:
    if env["res.partner"].search([("name", "=", name)]):
        continue
    p = env["res.partner"].create({"name": name, "is_company": True, "supplier_rank": 1,
                                   "country_id": env["res.country"].search([("code", "=", cc)], limit=1).id})
    env["res.partner.bank"].create({"partner_id": p.id, "acc_number": iban})
env.cr.commit()
print("SEEDED", env["res.partner"].search_count([("supplier_rank", ">", 0)]), env.company.name, env.company.currency_id.name)
