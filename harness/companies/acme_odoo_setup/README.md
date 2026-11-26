# Acme Components on Odoo 17: how the test company is set up

The company of the application skills is a real accounting application with invented data: Odoo 17 community from
source in a Python environment, PostgreSQL from the `pgserver` package. Nothing is installed in the system and no
service is touched; everything lives in one folder (`~/work/harness/company/` by default, `ACME_ODOO_HOME` to change it).

| Step | Script | What it does |
| --- | --- | --- |
| 1 | `setup_odoo.sh` | clones Odoo 17.0, makes the environment, installs its requirements |
| 2 | `init_odoo.sh` | starts PostgreSQL (`start_pg.py`) and creates the database `acme` with the accounting module |
| 3 | `seed.py` | the invented company: its name, the euro, eight suppliers each with a bank account on file |
| 4 | `template.sh` | loads the web client once (so its files exist), renames the database to `acme_tpl`, starts the server |
| after a restart of the machine | `start_pg.py`, then `serve_odoo.sh` | the server on `127.0.0.1:8069`, no scheduled jobs |

A run never works on `acme_tpl`: `harness/companies/acme_odoo.py` copies it into a database of its own, and drops the
copy when the run has been read and its screen kept. The screen needs a headless browser (`playwright install
chromium-headless-shell`); on a machine without `libasound.so.2`, unpack that library into `lib/` and put the folder on
`LD_LIBRARY_PATH`.

## In plain words

The test company is a real accounting application with made-up suppliers. Each test gets a fresh copy of it, so one
test cannot dirty the next, and the application's own screen is kept as the proof of what the agent entered.
