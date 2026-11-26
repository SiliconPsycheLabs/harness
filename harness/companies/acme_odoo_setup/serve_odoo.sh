#!/bin/bash
# The application server, on this machine only (127.0.0.1:8069). No scheduled jobs. It sees the runs' databases only,
# never the template they are copied from.
cd ~/work/harness/company
exec venv/bin/python odoo/odoo-bin --db_host=/home/user/work/harness/company/pgdata -r odoo -w odoo --data-dir=/home/user/work/harness/company/data --log-level=warn --http-interface=127.0.0.1 --http-port=8069 --max-cron-threads=0 --limit-time-real=600 --db-filter='^run_' "$@"
