"""Acme Components as a file tree (`harness/world.py`): the company of the document skills."""
from harness import world

CONTACTS = {"Northwind Bearings Ltd": "orders@northwind-bearings.example", "Harbor Tools Inc.": "sales@harbortools.example",
            "Tessitura Bellomo S.p.A.": "commerciale@tessiturabellomo.example", "Officine Galli S.r.l.": "ordini@officinegalli.example",
            "Atelier Dumont SARL": "contact@atelier-dumont.example", "Suministros Ibarra S.L.": "ventas@suministrosibarra.example",
            "Krämer Werkzeugbau GmbH": "vertrieb@kraemer-werkzeugbau.example", "Lindner Maschinenbau AG": "info@lindner-maschinenbau.example"}
READ, WRITE, REGISTER = world.READ, world.WRITE, {"mail_contacts": sorted(CONTACTS.values())}


def build(root, key):
    world.build(root)
    return root


def finish(handle, row, task):
    return {}
