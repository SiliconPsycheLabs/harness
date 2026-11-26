"""The company database: PostgreSQL from the pgserver package, kept running after this script ends."""
import pgserver

s = pgserver.get_server("/home/user/work/harness/company/pgdata", cleanup_mode=None)
print(s.get_uri())
try:
    s.psql("create role odoo with login createdb password $$odoo$$")
except Exception as x:  # the role is there from an earlier start
    print(str(x)[:120])
