"""The agent loop. The model asks for a tool call; the call goes to the gate; a call that passes runs, a call that does
not pass does not run and the model reads the gate's fixed reason. Every step keeps what it cost: tokens and seconds.

`enforce=False` is the shadow arm of a measurement: the gate's answer is recorded and every call runs.

Two ways to ask the model for a call. `mode="tools"`: the server's own tool calling. `mode="json"`: every step is one
JSON object the server is made to follow (`response_format`), for servers started without a tool-call parser and for
small models: {"action": "tool", "name": ..., "arguments": {...}} or {"action": "final", "content": ...}.
"""
import json
import time

REFUSED = "NOT ALLOWED by the company's rules: {reason}. The call did not run."


def tool_specs(skills):
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                               "parameters": t["inputSchema"]}} for s in skills for t in s.tools]


SHAPE_ONLY = ("pattern", "minLength", "maxLength", "minItems", "maxItems", "minimum", "maximum", "description")
JSON_HOW = ("\n\nAnswer with one JSON object and nothing else. To use a tool: {\"action\": \"tool\", \"name\": <tool name>, "
            "\"arguments\": {...}}. When you are done, or cannot go on: {\"action\": \"final\", \"content\": <your answer to the "
            "colleague>}.\n\nTools:\n")


def _shape(schema):
    """A tool's input schema with the limits taken out (lengths, patterns, ranges): what the server is made to follow.
    The limits are still checked, by the gate."""
    if isinstance(schema, dict):
        return {k: _shape(v) for k, v in schema.items() if k not in SHAPE_ONLY or isinstance(v, dict) and k == "description"}
    if isinstance(schema, list):
        return [_shape(v) for v in schema]
    return schema


def step_schema(skills):
    tools = [t for s in skills for t in s.tools]
    branches = [{"type": "object", "additionalProperties": False, "required": ["action", "name", "arguments"],
                 "properties": {"action": {"const": "tool"}, "name": {"const": t["name"]}, "arguments": _shape(t["inputSchema"])}}
                for t in tools]
    branches.append({"type": "object", "additionalProperties": False, "required": ["action", "content"],
                     "properties": {"action": {"const": "final"}, "content": {"type": "string"}}})
    return {"anyOf": branches}


def json_system(system, skills):
    lines = [f"- {t['name']}: {t.get('description', '')} Arguments: {json.dumps(t['inputSchema'], ensure_ascii=False)}"
             for s in skills for t in s.tools]
    return system + JSON_HOW + "\n".join(lines)


UNREAD = "NOT RUN: {reason}. It is a mistake in the text, not a rule of the company: correct it and call again."
NOTHING_DONE = ("NOTHING WAS DONE: no tool was called, so nothing changed in the company. Call the tools the job needs, one "
                "at a time, or say what stops you.")
NOT_FINISHED = "NOT FINISHED: {tools} was not called, so the result the colleague asked for does not exist yet. Call it now, or say what stops you."
HELD = "WAITING: {reason}. The {role} did not confirm it. The call did not run."


def run(chat, system, request, skills, box, root, enforce=True, max_steps=6, temperature=0, seed=0, max_tokens=4000,
        mode="tools", confirm=None, must_act=False, must_call=()):
    by_tool = {t["name"]: s for s in skills for t in s.tools}
    if mode == "json":
        system = json_system(system, skills)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": request}]
    out = {"steps": [], "final": "", "error": "", "tokens_in": 0, "tokens_out": 0, "model_seconds": 0.0, "model_calls": 0}
    t_start = time.time()
    for _ in range(max_steps):
        t0 = time.time()
        try:
            ask = {"messages": messages, "temperature": temperature, "seed": seed, "max_tokens": max_tokens}
            if mode == "json":
                ask["response_format"] = {"type": "json_schema", "json_schema": {"name": "step", "schema": step_schema(skills)}}
            else:
                ask["tools"] = tool_specs(skills)
            got = chat(ask)
        except Exception as x:  # noqa: BLE001  the row says what broke
            out["error"] = f"{type(x).__name__}: {x}"[:300]
            break
        out["model_seconds"] += time.time() - t0
        out["model_calls"] += 1
        usage = got.get("usage") or {}
        out["tokens_in"] += int(usage.get("prompt_tokens") or 0)
        out["tokens_out"] += int(usage.get("completion_tokens") or 0)
        msg = got["choices"][0]["message"]
        if mode == "json":
            text = str(msg.get("content") or "")
            try:
                obj = json.loads(text)
            except Exception:  # noqa: BLE001  an answer cut off or not JSON ends the run, and the row says so
                out["error"] = "the step is not a JSON object: " + text[:120]
                break
            messages.append({"role": "assistant", "content": text})
            if not isinstance(obj, dict) or obj.get("action") != "tool":
                if must_act and not out["steps"] and not out.get("answered_before_any_call"):
                    out["answered_before_any_call"] = 1   # a job that needs tools, answered with none: said once, by a fixed line
                    messages.append({"role": "user", "content": NOTHING_DONE})
                    continue
                if must_call and out["steps"] and not out.get("answered_before_the_closing_call") and not any(s["tool"] in must_call for s in out["steps"]):
                    out["answered_before_the_closing_call"] = 1   # the tool that makes the result was never called: said once
                    messages.append({"role": "user", "content": NOT_FINISHED.format(tools=" or ".join(must_call))})
                    continue
                out["final"] = str((obj or {}).get("content", "") if isinstance(obj, dict) else obj)[:1000]
                break
            calls = [{"id": "", "function": {"name": str(obj.get("name")), "arguments": json.dumps(obj.get("arguments"))}}]
        else:
            calls = msg.get("tool_calls") or []
            if not calls:
                if must_act and not out["steps"] and not out.get("answered_before_any_call"):
                    out["answered_before_any_call"] = 1
                    messages += [{"role": "assistant", "content": msg.get("content") or ""}, {"role": "user", "content": NOTHING_DONE}]
                    continue
                if must_call and out["steps"] and not out.get("answered_before_the_closing_call") and not any(s["tool"] in must_call for s in out["steps"]):
                    out["answered_before_the_closing_call"] = 1
                    messages += [{"role": "assistant", "content": msg.get("content") or ""}, {"role": "user", "content": NOT_FINISHED.format(tools=" or ".join(must_call))}]
                    continue
                out["final"] = str(msg.get("content") or "")[:1000]
                break
            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            name = c["function"]["name"]
            step = {"tool": name}
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise ValueError("not an object")
            except Exception:  # noqa: BLE001
                step.update(args=None, outcome="nopass", reason="the arguments are not a JSON object", rule="arguments", ran=False)
                reply = REFUSED.format(reason=step["reason"])
            else:
                step["args"] = args
                if name not in by_tool:
                    rec = {"outcome": "nopass", "reason": "no such tool", "rule": "tool"}
                else:
                    rec = box.decide(name, args)
                step.update(outcome=rec["outcome"], reason=rec.get("reason", ""), rule=rec.get("rule", ""))
                role = box.held_by(name, rec) if name in by_tool and hasattr(box, "held_by") else None
                if role:                               # the call waits for a person: asked once, and opened for this exact call
                    ok = bool(confirm and confirm(name, args))
                    step.update(held_for=role, confirmed=ok)
                    if ok and enforce and box.open_once(name, args, role) is None:
                        rec = box.decide(name, args)
                        step["outcome"] = rec["outcome"]
                if name in by_tool and (rec["outcome"] == "pass" or not enforce):
                    t1 = time.time()
                    try:
                        reply = str(by_tool[name].run(name, args, root))
                    except Exception as x:  # noqa: BLE001  a tool that cannot do what was asked says why
                        reply = f"ERROR: {type(x).__name__}: {x}"[:400]
                    step.update(ran=True, tool_seconds=round(time.time() - t1, 3))
                    if rec["outcome"] == "pass" and not reply.startswith("ERROR"):
                        box.ran(rec, reply)
                else:
                    step["ran"] = False
                    unread = str(rec.get("reason", "")).startswith("statement not understood")   # the gate's reader could not read the text
                    reply = (HELD.format(reason=step["reason"], role=role.replace("_", " ")) if role
                             else UNREAD.format(reason=rec["reason"]) if unread else REFUSED.format(reason=rec.get("reason", "")))
            step["reply"] = reply[:400]
            out["steps"].append(step)
            if mode == "json":
                messages.append({"role": "user", "content": f"TOOL RESULT ({name}): {reply}"})
            else:
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": reply})
    out["seconds"] = round(time.time() - t_start, 2)
    out["model_seconds"] = round(out["model_seconds"], 2)
    return out
