#!/bin/bash
# Odoo 17 community from source, with its own PostgreSQL from a Python package: no system package, no service touched.
set -x
cd ~/work/harness/company
[ -d odoo ] || git clone -q --depth 1 --branch 17.0 https://github.com/odoo/odoo.git
[ -d venv ] || ~/.local/bin/uv venv venv --python 3.12
grep -v -i -E "^(python-ldap|psycopg2)" odoo/requirements.txt > req.txt
~/.local/bin/uv pip install -q --python venv/bin/python -r req.txt psycopg2-binary pgserver
venv/bin/python -c "import psycopg2, pgserver, lxml, werkzeug; print('deps ok')"
echo SETUP_DONE
