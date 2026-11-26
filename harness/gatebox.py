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
                    expr = expr.replace("{{list:" + key + "}}", "[" + ", ".join(json.dumps(str(x), ensure_ascii=False) for x in values) + "]")
                t["doors"][tool].setdefault("requires", []).append({**c, "expr": expr})
    rights = {}
    for d in read:
        rights.setdefault(d.rstrip("/"), {})["read"] = True
    for d in write:
        rights.setdefault(d.rstrip("/"), {}).update(read=True, write=True)
    if rights:
        t["containers"] = rights
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

    def ran(self, rec, result=None):
        if rec.get("outcome") == "pass":
            _, self.state = manager.ran(self.table, rec, None, self.state, result)
