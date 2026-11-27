"""The database tools. The company's sales database is one SQLite file, `_db/acme.sqlite`, built when the run starts.
`run_query` runs whatever statement it is given, as a database does: what may run is the gate's business."""
import json
import os
import sqlite3


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def db_path(root):
    return os.path.join(str(root), "_db", "acme.sqlite")


def describe_database(root):
    c = sqlite3.connect(db_path(root))
    try:
        out = {}
        for (name,) in c.execute("select name from sqlite_master where type = 'table' order by name"):
            out[name] = [f"{r[1]} {r[2]}" for r in c.execute(f"pragma table_info({name})")]
        return json.dumps(out)
    finally:
        c.close()


def run_query(root, sql):
    os.makedirs(os.path.join(str(root), "_log"), exist_ok=True)
    with open(os.path.join(str(root), "_log", "queries.jsonl"), "a") as f:
        f.write(json.dumps(sql) + "\n")
    c = sqlite3.connect(db_path(root))
    try:
        cur = c.execute(sql)
        if cur.description is None:
            c.commit()
            return f"done: {cur.rowcount} row(s) changed"
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(51)
        text = json.dumps({"columns": cols, "rows": [list(r) for r in rows[:50]]}, ensure_ascii=False)
        return text + (" (first 50 rows: narrow the query)" if len(rows) > 50 else "")
    except sqlite3.Error as x:
        raise ValueError(f"the database refused the statement: {x}") from None
    finally:
        c.close()


def save_answer(root, path, question, answer, query):
    target = real(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump({"question": question, "answer": answer, "query": query}, f, ensure_ascii=False, indent=1)
    return f"saved {os.path.normpath('/' + str(path).lstrip('/'))}"
