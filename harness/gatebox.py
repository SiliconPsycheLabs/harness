"""The gate around a set of skills: the table is compiled from the tools' schemas, every call is decided by the
action manager of `gate_table`, and each answer is kept as the manager's own record (the tape's format).

The folders a path field may read or write are the company's limits: they are given here, not by the skill.
"""
import json

from gate_table import manager

from harness.tablec.mcp_table import table as compile_table


def build_table(skills, name, read=(), write=(), register=None):
    """One door per tool of every skill. `read` and `write` are the folders the company opens; `register` holds the
    company's own lists. A skill's `limits` are the company's rules on its tools: a tool closed with its reason, a
    field that must be one of a list of the company (`one_of`, with its own reason), a condition on the arguments
    (`requires`)."""
    import copy
    register = register or {}
    tools, languages = [], {}
    for s in skills:
        tools += copy.deepcopy(s.tools)
        languages.update(s.languages)
    t = compile_table({"tools": tools}, name, languages)
    for s in skills:
        lim = s.spec.get("limits", {})
        for tool, reason in lim.get("closed", {}).items():
            t["doors"][tool]["closed"] = reason
            t["doors"][tool].pop("requires", None)      # a closed door holds no conditions
        for where, rule in lim.get("one_of", {}).items():       # a field that must be one of a list of the company
            tool, field = where.split(".")
            names = ", ".join(json.dumps(str(x), ensure_ascii=False) for x in register[rule["list"]])
            t["doors"][tool].setdefault("requires", []).append(
                {"if": "expr", "expr": f'args.arguments["{field}"] in [{names}]', "else": rule["else"]})
        for tool, conds in lim.get("requires", {}).items():       # `{{list:NAME}}` in a condition is a list of the company
            for c in conds:
                expr = c["expr"]
                for key, values in register.items():
                    if isinstance(values, dict):          # `{{map:NAME}}`: a pairing of the company (a supplier and its bank account)
                        expr = expr.replace("{{map:" + key + "}}", "{" + ", ".join(
                            json.dumps(str(k), ensure_ascii=False) + ": " + json.dumps(str(v), ensure_ascii=False) for k, v in values.items()) + "}")
                    else:
                        expr = expr.replace("{{list:" + key + "}}", "[" + ", ".join(json.dumps(str(x), ensure_ascii=False) for x in values) + "]")
                t["doors"][tool].setdefault("requires", []).append({**c, "expr": expr})
        for tool, hold in lim.get("held", {}).items():          # the action waits for a person, who opens that exact action once
            role = hold["by"]
            t["doors"][tool]["lock"] = role
            t.setdefault("locks", {})[role] = {"open": [role], "edit": [role]}
            t["doors"][tool].setdefault("requires", []).append({"if": "expr", "expr": "false", "outcome": "ask", "else": hold["reason"]})
    for s in skills:                                              # the company's database: which table and column may be read or changed
        db = s.spec.get("limits", {}).get("database")
        if db:
            t.setdefault("schemas", {})["sql"] = {"tables": db["tables"]}
            t.setdefault("containers", {}).update(db["rights"])
    for s in skills:                                              # the outside hosts the company opens to a tool's web address
        for host in s.spec.get("limits", {}).get("hosts", []):
            t.setdefault("containers", {})[host] = {"connect": True}
    rights = {}
    for d in read:
        rights.setdefault(d.rstrip("/"), {})["read"] = True
    for d in write:
        rights.setdefault(d.rstrip("/"), {}).update(read=True, write=True)
    if rights:
        t["containers"] = {**t.get("containers", {}), **rights}
        t["schema"] = {"cwd": sorted(rights)[0], "containers": sorted(rights)}
    t["source"] = "compiled from the skills: " + ", ".join(f"{s.name} {s.version}" for s in skills)
    return t


class Box:
    """One session at the gate. `decide` returns the manager's record; `ran` moves the counters of a passed call."""

    def __init__(self, table):
        self.table, self.state, self.tape = table, None, []

    def decide(self, tool, args):
        rec, self.state = manager.decide(self.table, {"tool": tool, "args": {"arguments": args}}, None, self.state)
        self.tape.append(rec)
        return rec

    def held_by(self, tool, rec):
        """The role a stopped call waits for, when the rule that stopped it is a confirmation and not a refusal."""
        door = self.table["doors"].get(tool, {})
        m = rec.get("rule", "").rsplit("#", 1)
        if rec.get("outcome") == "pass" or len(m) != 2 or not m[1].isdigit() or not door.get("lock"):
            return None
        reqs = door.get("requires", [])
        i = int(m[1]) - 1
        return door["lock"] if 0 <= i < len(reqs) and reqs[i].get("outcome") == "ask" else None

    def open_once(self, tool, args, by):
        why, self.state = manager.open_once(self.table, tool, {"arguments": args}, by, None, self.state)
        return why

    def ran(self, rec, result=None):
        if rec.get("outcome") == "pass":
            _, self.state = manager.ran(self.table, rec, None, self.state, result)
