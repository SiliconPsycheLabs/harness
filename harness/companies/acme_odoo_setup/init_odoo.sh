#!/bin/bash
cd ~/work/harness/company
venv/bin/python start_pg.py
venv/bin/python odoo/odoo-bin -d acme --db_host=/home/user/work/harness/company/pgdata -r odoo -w odoo -i account --without-demo=all --stop-after-init --no-http --data-dir=/home/user/work/harness/company/data --log-level=warn
echo INIT_DONE $?
