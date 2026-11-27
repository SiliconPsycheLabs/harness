"""Acme Components as a whole office: the file tree (inbox, documents, outbox) and the accounting application (Odoo),
for a role that reads a document, works in the application and writes a mail."""
from harness import world
from harness.companies import acme_files, acme_odoo

READ, WRITE = world.READ, world.WRITE
REGISTER = {**acme_files.REGISTER, **acme_odoo.REGISTER}


def build(root, key):
    world.build(root)
    return acme_odoo.build(root, key)


finish = acme_odoo.finish
