#!/bin/bash
# From the seeded database `acme` to the template `acme_tpl` every run is copied from.
cd ~/work/harness/company
O="venv/bin/python odoo/odoo-bin"; A="--db_host=/home/user/work/harness/company/pgdata -r odoo -w odoo --data-dir=/home/user/work/harness/company/data --log-level=warn"
$O shell -d acme $A --no-http < seed.py 2>&1 | grep -E "SEEDED|Error" | tail -2
pkill -f "odoo-bin.*--http-port=8069"; sleep 2
(setsid nohup bash serve_odoo.sh --db-filter='^acme$' > odoo_server.log 2>&1 < /dev/null &)
until curl -s -m 5 -o /dev/null http://127.0.0.1:8069/web/login; do sleep 3; done
# the web client once, so its compiled files are in the filestore the runs copy
LD_LIBRARY_PATH=~/work/harness/company/lib ~/work/harness/venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 860})
    pg.goto("http://127.0.0.1:8069/web/login?db=acme")
    pg.fill("input[name=login]", "admin"); pg.fill("input[name=password]", "admin"); pg.click("button[type=submit]")
    pg.wait_for_selector(".o_main_navbar", timeout=180000)
    pg.goto("http://127.0.0.1:8069/web#action=account.action_move_in_invoice_type")
    pg.wait_for_selector(".o_list_view, .o_view_nocontent", timeout=180000)
    pg.wait_for_timeout(2000)
    pg.screenshot(path="template_screen.png")
    print("WEB CLIENT LOADED")
    b.close()
PY
pkill -f "odoo-bin.*--http-port=8069"; sleep 3
venv/bin/python - <<'PY'
import psycopg2
c = psycopg2.connect(host="/home/user/work/harness/company/pgdata", user="odoo", password="odoo", dbname="postgres"); c.autocommit = True
cur = c.cursor()
cur.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname in ('acme','acme_tpl') and pid <> pg_backend_pid()")
cur.execute('DROP DATABASE IF EXISTS "acme_tpl"')
cur.execute('ALTER DATABASE "acme" RENAME TO "acme_tpl"')
print("TEMPLATE READY")
PY
rm -rf data/filestore/acme_tpl; mv data/filestore/acme data/filestore/acme_tpl 2>/dev/null
setsid nohup bash serve_odoo.sh > odoo_server.log 2>&1 < /dev/null &
until curl -s -m 5 -o /dev/null http://127.0.0.1:8069/web/database/selector; do sleep 3; done
echo TEMPLATE_DONE
