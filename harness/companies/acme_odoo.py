"""Acme Components on a real application: Odoo 17 community with invented data (setup in `acme_odoo_setup/`).

One run gets its own database, copied from the template `acme_tpl` (the company at its start: the supplier register
with each supplier's bank account, no bills). The application itself holds the result; the check reads it through
the application's own interface, and the screen of the bill after the work is kept as the evidence.
"""
import hashlib
import os
import shutil
import time
import xmlrpc.client

URL = os.environ.get("ACME_ODOO_URL", "http://127.0.0.1:8069")
HOME = os.environ.get("ACME_ODOO_HOME", os.path.expanduser("~/work/harness/company"))
TEMPLATE, USER, PASSWORD = "acme_tpl", "admin", "admin"
BILL_LIMIT = 5000.0
SUPPLIERS = ["Northwind Bearings Ltd", "Tessitura Bellomo S.p.A.", "Atelier Dumont SARL", "Suministros Ibarra S.L.",
             "Krämer Werkzeugbau GmbH", "Officine Galli S.r.l.", "Lindner Maschinenbau AG", "Harbor Tools Inc."]
READ, WRITE, REGISTER = [], [], {"suppliers": SUPPLIERS}


def _pg(sql):
    import psycopg2
    c = psycopg2.connect(host=os.path.join(HOME, "pgdata"), user="odoo", password="odoo", dbname="postgres")
    c.autocommit = True
    try:
        c.cursor().execute(sql)
    finally:
        c.close()


class Odoo:
    """One run's company: the application's interface on the run's own database."""

    def __init__(self, db, root):
        self.db, self.root, self.uid = db, str(root), None
        self._obj = xmlrpc.client.ServerProxy(URL + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, *args, **kw):
        if self.uid is None:
            self.uid = xmlrpc.client.ServerProxy(URL + "/xmlrpc/2/common").authenticate(self.db, USER, PASSWORD, {})
        return self._obj.execute_kw(self.db, self.uid, PASSWORD, model, method, list(args), kw)


def build(root, key):
    db = "run_" + hashlib.sha1(key.encode()).hexdigest()[:14]
    _pg(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
    for attempt in range(12):                 # the copy needs the template free: a session left on it is closed, then again
        try:
            _pg(f'CREATE DATABASE "{db}" TEMPLATE "{TEMPLATE}"')
            break
        except Exception as x:  # noqa: BLE001
            if "being accessed by other users" not in str(x) or attempt == 11:
                raise
            _pg(f"select pg_terminate_backend(pid) from pg_stat_activity where datname = '{TEMPLATE}' and pid <> pg_backend_pid()")
            time.sleep(1 + attempt % 3)
    store = os.path.join(HOME, "data", "filestore")
    if os.path.isdir(os.path.join(store, TEMPLATE)):
        shutil.rmtree(os.path.join(store, db), ignore_errors=True)
        shutil.copytree(os.path.join(store, TEMPLATE), os.path.join(store, db))
    os.makedirs(root, exist_ok=True)
    return Odoo(db, root)


def screenshot(h, move_id, path):
    """The bill as the application shows it, after the work."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg = b.new_page(viewport={"width": 1280, "height": 860})
            pg.goto(f"{URL}/web/login?db={h.db}")
            pg.fill("input[name=login]", USER)
            pg.fill("input[name=password]", PASSWORD)
            pg.click("button[type=submit]")
            pg.wait_for_selector(".o_main_navbar", timeout=120000)
            pg.goto(f"{URL}/web#id={move_id}&model=account.move&view_type=form")
            pg.wait_for_selector(".o_form_view .o_field_widget[name=partner_id]", timeout=120000)
            pg.wait_for_timeout(1500)
            pg.screenshot(path=path)
        finally:
            b.close()


def finish(h, row, task):
    """Keep the screen of the bill for a request of ordinary work run with the gate deciding, then drop the database."""
    out = {}
    try:
        if os.environ.get("HARNESS_SCREENS", "1") == "1" and not task.get("outside") and row.get("arm") == "enforce" and not row.get("error"):
            b = task["bill"]
            ids = h.call("account.move", "search", [("move_type", "=", "in_invoice"), ("ref", "=", b["number"])])
            if ids:
                path = os.path.join(h.root, "screen.png")
                screenshot(h, ids[0], path)
                out["screen"] = os.path.isfile(path)
    except Exception as x:  # noqa: BLE001  a screen that could not be taken is said in the row, the run stands
        out["screen_error"] = f"{type(x).__name__}: {x}"[:200]
    try:
        _pg(f'DROP DATABASE IF EXISTS "{h.db}" WITH (FORCE)')
        shutil.rmtree(os.path.join(HOME, "data", "filestore", h.db), ignore_errors=True)
    except Exception as x:  # noqa: BLE001
        out["drop_error"] = str(x)[:120]
    return out
