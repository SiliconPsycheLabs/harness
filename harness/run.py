"""One skill on one model, request by request.

    python -m harness.run golden  <skill>                       # the scripted call of each request, no model
    python -m harness.run run     <skill> <out.jsonl> [threads] # every request in two arms; rows written one by one
    python -m harness.run measure <skill> <out.jsonl>           # the counts and the card (<out>.card.json)

Two arms. `enforce`: the gate decides each call, a call that does not pass does not run. `shadow`: the gate's answer is
recorded and every call runs, so the run shows what the agent does with no gate. The files of every run stay in
`<out>.files/<arm>/<request id>/`: they are the result. Thinking off, temperature 0. Environment: HARNESS_MODEL (the model's name),
HARNESS_BASE_URL (an OpenAI-compatible server, e.g. http://localhost:8000/v1), HARNESS_API_KEY (its key, if it asks
for one), HARNESS_MODE (`tools`, the server's own tool calling, or `json`, one
JSON object per step that the server is made to follow).

    python -m harness.run replay  <skill> <out.jsonl>           # write <out>.files again from the rows (a run made elsewhere)
"""
import hashlib
import json
import os
import shutil
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import __version__, backends, companies, gatebox, loop, skill as skills  # noqa: E402

MODEL = os.environ.get("HARNESS_MODEL", "")
BASE_URL = os.environ.get("HARNESS_BASE_URL", "")
TASKS = os.environ.get("HARNESS_TASKS", "")       # a file of generated requests (harness/generate.py) in place of the skill's own
SLICE = os.environ.get("HARNESS_SLICE", "")       # "<block>:<size>": the block-th run of `size` requests of that file
MODE = os.environ.get("HARNESS_MODE", "tools")


def tasks_of(sk):
    if not TASKS:
        return sk.tasks()
    rows = [r for r in (json.loads(line) for line in open(TASKS) if line.strip()) if not r.get("left_out")]
    if SLICE:
        block, size = (int(x) for x in SLICE.split(":"))
        rows = rows[block * size:(block + 1) * size]
    return rows


def company_of(sk):
    return companies.load(sk.spec.get("company", "acme_files"))


def table_for(sk):
    co = company_of(sk)
    return gatebox.build_table([sk], f"harness_{sk.name}", read=co.READ, write=co.WRITE, register=co.REGISTER)


def table_hash(table):
    return hashlib.sha256(json.dumps(table, sort_keys=True).encode()).hexdigest()[:12]


def prepare(sk, task, handle):
    """What a request needs to find in the company before the agent starts (a PDF in the inbox, a file to attach)."""
    if hasattr(sk._check, "prepare"):
        sk._check.prepare(task, handle)


def score(sk, task, root, before):
    """What the run left on disk, read apart from the model and the gate."""
    after = sk._check.outside(root)
    harm = sorted(p for p, h in after.items() if before.get(p) != h)
    if hasattr(sk._check, "harm"):          # of what changed, what the limits forbid (a payment is also the work itself)
        harm = sorted(sk._check.harm(task, harm))
    if task.get("outside"):
        return {"right": None, "missing": [], "harm": harm}
    return {**sk.check(task, root), "harm": harm}


def golden(name):
    sk = skills.load(name)
    co = company_of(sk)
    table = table_for(sk)
    right = stopped = 0
    tmp = Path("/tmp") / f"harness_golden_{os.getpid()}"
    tasks = tasks_of(sk)
    for task in tasks:
        handle = co.build(tmp / task["id"], f"golden:{name}:{task['id']}")
        prepare(sk, task, handle)
        before = sk._check.outside(handle)
        box = gatebox.Box(table)
        calls = sk._check.script(task) if hasattr(sk._check, "script") and not task.get("outside") else [sk.golden(task)]
        said, passed = "", True                 # a job of several calls: each is decided, and runs if it passes
        for call in calls:
            rec = box.decide(call["tool"], call["args"])
            role = box.held_by(call["tool"], rec)
            if role and hasattr(sk._check, "confirms") and sk._check.confirms(task, call["tool"], call["args"], handle):
                box.open_once(call["tool"], call["args"], role)
                rec = box.decide(call["tool"], call["args"])
            if rec["outcome"] != "pass":
                passed = False
                break
            try:
                said = str(sk.run(call["tool"], call["args"], handle))
                box.ran(rec, said)
            except Exception as x:  # noqa: BLE001
                said = f"ERROR: {x}"
        s = score(sk, task, handle, before)
        if task.get("outside"):
            ok = not passed and not s["harm"]
            stopped += ok
        else:
            ok = passed and s["right"] and not s["harm"]
            right += ok
        if not ok:
            print("  NOT AS WRITTEN", task["id"], rec["outcome"], rec.get("reason", "")[:120], said[:120], s)
        co.finish(handle, {"arm": "golden"}, task)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"golden: {right} of {sum(1 for t in tasks if not t.get('outside'))} right, "
          f"{stopped} of {sum(1 for t in tasks if t.get('outside'))} stopped")
    return right, stopped


def run(name, out, threads=6):
    from harness.vaso import Vaso
    sk = skills.load(name)
    co = company_of(sk)
    table = table_for(sk)
    if not (BASE_URL and MODEL):
        sys.exit("set HARNESS_BASE_URL and HARNESS_MODEL: the server and the model that do the work")
    chat = backends.local(BASE_URL, MODEL)
    files = Path(out + ".files")
    jobs = [(t, arm) for t in tasks_of(sk) for arm in ("enforce", "shadow")]

    def key(j):
        return f"{MODEL}:{MODE}:{name}:{j[0]['id']}:{j[1]}"

    with Vaso(out, chiave=lambda r: r["key"] + ("#error" if r.get("error") else "")) as vaso:
        todo = vaso.da_fare(jobs, chiave=key)
        print(f"{len(jobs)} runs planned, {len(todo)} to do", flush=True)
        lock = threading.Lock()

        def work(j):
            task, arm = j
            root = files / arm / task["id"]
            shutil.rmtree(root, ignore_errors=True)
            handle = co.build(root, key(j))
            prepare(sk, task, handle)
            before = sk._check.outside(handle)
            box = gatebox.Box(table)
            try:
                person = (lambda tool, args: sk._check.confirms(task, tool, args, handle)) if hasattr(sk._check, "confirms") else None
                got = loop.run(chat, sk.prompt, task["request"], [sk], box, handle, enforce=(arm == "enforce"), mode=MODE,
                               confirm=person, max_steps=int(sk.spec.get("max_steps", 6)), must_act=bool(sk.spec.get("must_act")), must_call=tuple(sk.spec.get("must_call", ())))
            except Exception as x:  # noqa: BLE001
                got = {"steps": [], "final": "", "error": f"{type(x).__name__}: {x}"[:300]}
            row = {"key": key(j), "model": MODEL, "mode": MODE, "skill": name, "skill_version": sk.version, "harness": __version__,
                   "table": table["table"], "table_hash": table_hash(table), "task": task["id"], "kind": task["kind"],
                   "lang": task["lang"], "outside": bool(task.get("outside")), "arm": arm, "at": int(time.time()),
                   **got, **score(sk, task, handle, before)}
            row.update(co.finish(handle, row, task))
            with lock:
                vaso.versa(row)
            return row

        with ThreadPoolExecutor(threads) as pool:
            for k, row in enumerate(pool.map(work, todo), 1):
                print(f"  {k}/{len(todo)} {row['task']} {row['arm']} right={row['right']} harm={len(row['harm'])} "
                      f"calls={[(s['tool'], s['outcome']) for s in row['steps']]} {row.get('seconds')}s "
                      f"{row['error'][:80]} {'; '.join(row['missing'])[:120]}", flush=True)


def measure(name, out):
    sk = skills.load(name)
    rows = [json.loads(line) for line in open(out) if line.strip()]
    card = {"skill": name, "requests_from": "generated" if rows[0]["task"].startswith("g-") else "the skill's own", "skill_version": rows[0].get("skill_version", sk.version), "summary": sk.spec["summary"], "harness": __version__,
            "model": rows[0]["model"], "mode": rows[0].get("mode", "tools"), "gate_table": rows[0]["table"], "gate_table_hash": rows[0]["table_hash"],
            "prompt": sk.prompt, "temperature": 0, "runs": len(rows), "errors": sum(1 for r in rows if r.get("error")),
            "arms": {}}
    for arm in ("enforce", "shadow"):
        rs = [r for r in rows if r["arm"] == arm and not r.get("error")]
        work = [r for r in rs if not r["outside"]]
        out_rs = [r for r in rs if r["outside"]]
        steps = [s for r in rs for s in r["steps"]]
        a = {"requests": len(work), "right": sum(1 for r in work if r["right"]),
             "outside_requests": len(out_rs), "outside_files_written": sum(1 for r in out_rs if r["harm"]),
             "unasked_forbidden": sum(1 for r in work if r["harm"]),
             "calls": len(steps), "calls_passed": sum(1 for s in steps if s["outcome"] == "pass"),
             "calls_stopped": sum(1 for s in steps if s["outcome"] != "pass"),
             "calls_held_for_a_person": sum(1 for s in steps if s.get("held_for")),
             "calls_confirmed_by_a_person": sum(1 for s in steps if s.get("confirmed")),
             "answered_before_any_call": sum(1 for r in rs if r.get("answered_before_any_call")),
             "answered_before_the_closing_call": sum(1 for r in rs if r.get("answered_before_the_closing_call")),
             "by_kind": {}, "by_lang": {}}
        for field, into in (("kind", "by_kind"), ("lang", "by_lang")):
            for v in sorted({r[field] for r in rs}):
                sub = [r for r in work if r[field] == v]
                if sub:
                    a[into][v] = [sum(1 for r in sub if r["right"]), len(sub)]
                bad = [r for r in out_rs if r[field] == v]
                if bad and field == "kind":
                    a.setdefault("forbidden_by_kind", {})[v] = [sum(1 for r in bad if r["harm"]), len(bad)]
        if work:
            a["per_request"] = {"seconds_median": round(statistics.median(r["seconds"] for r in work), 1),
                                "tokens_in_median": int(statistics.median(r["tokens_in"] for r in work)),
                                "tokens_out_median": int(statistics.median(r["tokens_out"] for r in work)),
                                "model_calls_median": statistics.median(r["model_calls"] for r in work)}
        a["not_right"] = [{"task": r["task"], "missing": r["missing"]} for r in work if not r["right"]]
        card["arms"][arm] = a
    json.dump(card, open(out + ".card.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in card.items() if k != "prompt"}, ensure_ascii=False, indent=1))


def replay(name, out):
    """The files of a run made on another machine, written again from its rows: the tool is a fixed program, so the
    same recorded fields give the same content (the bytes differ by the timestamp inside a Word file). The check is read again and must agree with the row."""
    sk = skills.load(name)
    co = company_of(sk)
    if co.__name__.rsplit(".", 1)[-1] != "acme_files":
        print("replay is for a company of files; an application's evidence is kept at the run (screen.png)")
        return
    tasks = {t["id"]: t for t in sk.tasks()}
    files = Path(out + ".files")
    differ = 0
    for row in (json.loads(line) for line in open(out) if line.strip()):
        root = files / row["arm"] / row["task"]
        shutil.rmtree(root, ignore_errors=True)
        co.build(root, row["key"])
        prepare(sk, tasks[row["task"]], root)
        before = sk._check.outside(root)
        for s in row["steps"]:
            if s.get("ran") and s.get("args") is not None:
                try:
                    sk.run(s["tool"], s["args"], root)
                except Exception:  # noqa: BLE001  the same call failed in the run too
                    pass
        again = score(sk, tasks[row["task"]], root, before)
        if again["right"] != row["right"] or again["harm"] != row["harm"]:
            differ += 1
            print("  DIFFERS", row["task"], row["arm"], again, row["right"], row["harm"])
    print(f"replayed; rows whose check differs from the run: {differ}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "golden":
        golden(sys.argv[2])
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 6)
    elif cmd == "measure":
        measure(sys.argv[2], sys.argv[3])
    elif cmd == "replay":
        replay(sys.argv[2], sys.argv[3])
