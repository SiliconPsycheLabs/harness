"""A gate table compiled from the tools an MCP server declares.

    python mcp_table.py <tools.json> <out.json> [languages.json]

`tools.json` is what the server answers to `tools/list`: `{"tools": [{"name", "inputSchema", "annotations"}, ...]}`.
One door per tool, its arguments under `arguments` (`{"arguments": {...}}`), checked by one condition compiled from the
tool's input schema with the schema compiler of `openapi_table.py` (types, required, extra properties, lengths, ranges,
patterns, enums, constants, nested objects and arrays). A construct the compiler does not know stops the compile. The
door keeps the tool's annotations as `hints`; whether a destructive tool is open at all is the company's decision,
written in the table like any other closed door.

**A field that carries a text in a language** (a shell command, an SQL statement, a web address) is read by that
language's translator, like the same text sent as a `shell`, `sql` or `url` action: a command inside a tool meets the
shell rules, an address inside a fetch meets the hosts the table opens. `languages.json` says which field is in which
language, one row per tool and field, written and signed by a person: `{"execute_command": {"command": "shell"},
"fetch": {"url": "url"}, "move_file": {"source": "path_write"}, "search": {"query": "text"}}` (`text` is plain words,
not read). A top-level string field
whose name says it carries a command, a statement or an address (`command`, `sql`, `url` ...) and that has no row
closes its tool, naming the field: the compiler never guesses a language, and never lets such a field pass unread.
A path field (`path`, `source`) is read against the table's folders when its row says `path_read` or `path_write`.
"""
import json
import sys

from harness.tablec.openapi_table import Compiler

LANGUAGES = {"shell", "sql", "url", "path_read", "path_write", "text", "target", "target_url", "nmap_options", "nmap_scripts",
             "masscan_target", "masscan_options", "sqlmap_options", "ffuf_options", "gobuster_options", "ferox_options", "dirsearch_options", "hydra_options", "nikto_options", "nuclei_options", "katana_options", "subfinder_options", "hakrawler_options", "arjun_options", "fierce_options", "wafw00f_options", "smbmap_options", "gau_options", "dalfox_options", "rustscan_options", "enum4linux_ng_options", "dirb_options", "nbtscan_options", "dnsenum_options", "enum4linux_options", "dotdotpwn_options", "xsser_options", "responder_options", "x8_options", "arp_scan_options", "amass_options", "wpscan_options", "rpcclient_options", "rpcclient_commands_text", "strings_options", "objdump_options", "xxd_options", "exiftool_options", "exiftool_flag", "foremost_options", "trivy_options", "checkov_options", "ropgadget_options", "ropper_options", "one_gadget_options", "anew_options", "qsreplace_options", "binwalk_options", "hashpump_options", "john_options", "gdb_options", "radare2_files", "uro_options", "kube_hunter_options"}
# Field names that carry a command, a statement or an address: such a field needs a signed row before its tool opens.
NEEDS_A_ROW = {"command", "cmd", "commands", "shell", "script", "code", "exec", "args_line", "commandline", "command_line",
               "sql", "query", "statement", "stmt",
               "url", "uri", "href", "link", "endpoint", "webhook", "webhook_url", "target_url", "callback_url"}


def table(listing, name="mcp", languages=None, schema_only=False, needs_a_row=()):
    """`schema_only`: the doors check the input schemas and nothing else.
    `needs_a_row`: more field names that close their tool until a signed row names their language (the pentest tables
    add the target fields: `target`, `host`, `domain` ...)."""
    languages = languages or {}
    c = Compiler({"components": {"schemas": {}}})
    doors = {}
    for t in listing["tools"]:
        expr = c.schema(t["inputSchema"], "args.arguments")
        door = {"form": {"arguments": "object"}, "hints": t.get("annotations", {}),
                "requires": [{"if": "expr", "expr": expr, "else": "the arguments do not follow the tool's input schema"}]}
        doors[t["name"]] = door
        if schema_only:
            continue
        signed = languages.get(t["name"], {})
        for field, lang in signed.items():
            if lang not in LANGUAGES:
                raise ValueError(f"{t['name']}.{field}: language {lang!r} is not one of {sorted(LANGUAGES)}")
        props = t["inputSchema"].get("properties", {})
        for field in signed:
            if field not in props:
                raise ValueError(f"{t['name']}.{field}: the tool declares no such field")
        unread = sorted(f for f, s in props.items()
                        if (f.lower() in NEEDS_A_ROW or f.lower() in needs_a_row) and s.get("type", "string") == "string"
                        and f not in signed)
        read = [{"language": lang, "arg": f"arguments.{f}"} for f, lang in sorted(signed.items()) if lang != "text"]
        if unread:
            door["closed"] = (f"the field {', '.join(unread)} of this tool carries a command, a statement or an address "
                              "the table does not read yet: a person names its language")
            door.pop("requires", None)          # a closed door holds no conditions: the console's validator refuses both
        if read:
            door["languages"] = read
    return {"table": name, "version": 1, "doors": doors}


if __name__ == "__main__":
    langs = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
    out = table(json.load(open(sys.argv[1])), "mcp_files", langs)
    json.dump(out, open(sys.argv[2], "w"), indent=1)
    print(len(out["doors"]), "doors")
