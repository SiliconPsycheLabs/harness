"""A gate table compiled from an OpenAPI 3.0 document.

One door per operation (its `operationId`), routed by method and path template (`reader_http.route`). Each door has
the same form (`path`, `query`, `header`, `body`, all objects) and its conditions are written in the table's own
expression language (CEL), one per parameter and one for the body, so the table holds the company's rules as data and
the engine reads them like any other table. What a request may carry is what the document says:

- a parameter the document marks `required` must be there; a parameter that is there must read as its type (path,
  query and header values arrive as text: an integer is digits with an optional sign, a number as decimal text, a
  boolean `true` or `false`), stay inside the range its `format` gives (`int32`, `int64`), and be one of its `enum`;
- a body the document marks `required` must be there; a body that is there must follow its schema: types, required
  properties, enums, formats (`int32`, `int64`, `date-time`), items of arrays, nested objects through `$ref`.

A schema construct this compiler does not know (`oneOf`, `pattern`, `minimum` ...) stops the compile with its name:
the table is never built looser than the document. Security: an API key must be in its place; a bearer,
OAuth 2 or OpenID Connect scheme needs an Authorization header (the token is checked by its issuer).

    python openapi_table.py <openapi.yaml|json> <out.json> [base path] [--closed]

Form bodies (`application/x-www-form-urlencoded`) and `deepObject` query parameters are read by `reader_http` into the
structure their brackets name (`a[b][0]=x`); their schemas are compiled with every leaf as text (`form`). `anyOf` and
`oneOf` are compiled as alternatives, `additionalProperties` as a schema for the keys not listed. Vendor extensions
(`x-...`) that say nothing about what a request may carry are skipped by name; any other construct stops the compile.
"""
import json
import sys

INT_RANGE = {"int32": (-2 ** 31, 2 ** 31 - 1), "int64": (-2 ** 63, 2 ** 63 - 1)}
KNOWN = {"writeOnly", "contentEncoding", "contentMediaType", "examples", "errorMessage", "type", "format", "enum", "items", "properties", "required", "$ref", "description", "example", "xml",
         "default", "x-swagger-router-model", "nullable", "title", "additionalProperties", "minLength", "maxLength",
         "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems", "pattern", "const",
         "anyOf", "oneOf", "deprecated", "x-stripeBypassValidation", "x-expandableFields", "x-expansionResources",
         "x-resourceId", "x-stripeMostCommon", "x-stripeResource", "x-stripeOperations",
         "$schema", "$id", "$comment",   # what a document says about itself: no constraint on the value
         "allOf", "uniqueItems", "minProperties", "maxProperties",
         "readOnly", "discriminator", "x-github", "x-github-breaking-changes", "x-multi-segment"}  # GitHub's document
NOTES = {"description", "title", "example", "xml", "default", "deprecated", "x-swagger-router-model", "x-github",
         "x-github-breaking-changes", "x-multi-segment", "discriminator", "readOnly", "$schema", "$id", "$comment"}
DECIMAL = r"^-?([0-9]+([.][0-9]*)?|[.][0-9]+)$"    # a decimal written as text (Stripe's `format: decimal`)
LEAP = r"([0-9]{2}(0[48]|[2468][048]|[13579][26])|([02468][048]|[13579][26])00)"
DATE = (r"([0-9]{4}-((0[13578]|1[02])-(0[1-9]|[12][0-9]|3[01])|(0[469]|11)-(0[1-9]|[12][0-9]|30)|02-(0[1-9]|1[0-9]|2[0-8]))"
        r"|" + LEAP + r"-02-29)")
DATE_TIME = (r"^" + DATE + r"[Tt]([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]+)?([Zz]|[+-]([01][0-9]|2[0-3]):[0-5][0-9])$")


class NotReadable(ValueError):
    """An operation the document does not describe well enough to compile: its door is closed with the reason."""


class RecursiveSchema(NotReadable):
    """A schema that contains itself (a filter of filters): CEL here is written out in full, so it cannot hold one."""


def lit(x):
    return json.dumps(x)


class Compiler:
    def __init__(self, doc, closed=False):
        """`closed`: read as Stripe reads a request: a query parameter the operation does not declare is
        not taken; an empty value unsets a field, so a text field takes "" only where the document lists "" and a
        required field left empty is missing; an empty `limit` is not given, any other empty query value is read as
        written; an integer is 64 bits; a `unix-time` integer does not take -0. Without it,
        as OpenAPI reads a document, an extra query parameter is ignored."""
        self.doc = doc
        self.closed = closed

    def resolve(self, s):
        while "$ref" in s:
            section, name = s["$ref"].split("/")[-2:]
            s = self.doc["components"][section][name]
        return self.norm(s)

    @staticmethod
    def norm(s):
        """One reading for the two OpenAPI versions. OpenAPI 3.1 (JSON Schema 2020-12) writes `type` as a list
        (`["string", "null"]`): one type and null is that type, nullable; several types are alternatives. OpenAPI 3.0
        writes `exclusiveMinimum`/`exclusiveMaximum` as a flag on `minimum`/`maximum`; 3.1 as the bound itself, which
        is how the compiler reads it: `{"minimum": 0, "exclusiveMinimum": true}` becomes `{"exclusiveMinimum": 0}`, a
        false flag is dropped (read as a number before, a flag made a bound of 0 or 1: Cloudflare has 160)."""
        if not isinstance(s, dict):
            return s
        out = s
        if isinstance(s.get("type"), list):
            kinds = [k for k in s["type"] if k != "null"]
            out = {k: v for k, v in s.items() if k != "type"}
            if "null" in s["type"]:
                out["nullable"] = True
            if len(kinds) == 1:
                out["type"] = kinds[0]
            elif kinds:
                out["anyOf"] = [{"type": k} for k in kinds]
        for flag, bound in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
            if isinstance(out.get(flag), bool):
                out = dict(out)
                if out.pop(flag) and bound in out:
                    out[flag] = out.pop(bound)
        return out

    def all_of(self, s, e, depth, compile_one):
        """`allOf`: every part holds, and so do the keys beside it (a schema written next to its parts)."""
        if "allOf" not in s:
            return ""
        rest = {k: v for k, v in s.items() if k != "allOf"}
        subs = [f"({compile_one(x, e, depth + 1)})" for x in s["allOf"]]
        if set(rest) - NOTES:
            subs.append(f"({compile_one(rest, e, depth + 1)})")
        return "(" + " && ".join(subs) + ")"

    def wanted(self, s):
        """The properties a request must carry: `required`, less those the document marks read-only (OpenAPI 3.0:
        `required` on a read-only property applies to responses only)."""
        props = s.get("properties", {})
        return [r for r in s.get("required", []) if not self.resolve(props.get(r, {})).get("readOnly")]

    @staticmethod
    def unknown(s, also=()):
        """The keys of a schema this compiler does not read. A vendor extension (`x-...`) says nothing about what a
        request may carry (OpenAPI: extensions never change validation), so it is skipped whatever its name."""
        return {k for k in set(s) - KNOWN - set(also) if not k.startswith("x-")}

    def schema(self, s, e, depth=0):
        """CEL that is true when the JSON value `e` follows the schema `s`. A schema met again inside itself (through
        `$ref`) raises `RecursiveSchema`: the operation's door is then closed, never compiled looser."""
        ref = s.get("$ref") if isinstance(s, dict) else None
        stack = self.__dict__.setdefault("_refs", [])
        if ref is not None and ref in stack:
            raise RecursiveSchema(f"the document's schema {ref.split('/')[-1]} contains itself")
        if ref is not None:
            stack.append(ref)
        try:
            return self._schema(s, e, depth)
        finally:
            if ref is not None:
                stack.pop()

    def _schema(self, s, e, depth=0):
        s = self.resolve(s)
        if s.get("nullable") is True:        # OpenAPI 3.0 `nullable`, 3.1 `"null"` in `type`: null is a value it takes
            rest = self._schema({k: v for k, v in s.items() if k != "nullable"}, e, depth)
            return f"({e} == null ? true : ({rest or 'true'}))"
        if "not" in s:                       # JSON Schema `not`: the value follows the rest and does not follow `not`
            rest = self.schema({k: v for k, v in s.items() if k != "not"}, e, depth) or "true"
            return f"({rest}) && !({self.schema(s['not'], e, depth + 1) or 'true'})"
        unknown = self.unknown(s, ("not", "multipleOf", "propertyNames"))
        if unknown:
            raise ValueError(f"schema construct not compiled: {sorted(unknown)}")
        t, parts = s.get("type"), []
        both = self.all_of(s, e, depth, self.schema)
        if both:
            return both
        alts = self.alternatives(s, e, depth, self.schema)
        if alts:
            return alts
        # Each read inside a value is guarded by the conditional operator, as in `form`: the expression library
        # gives an error, not false, for a comprehension over a value that is not there, even on the side of an `||`
        # that is already true (a missing optional parent made every valid body fail).
        if t == "object" or (t is None and ("properties" in s or "required" in s)):
            obj = [f"{lit(r)} in {e}" for r in self.wanted(s)]
            if "minProperties" in s:
                obj.append(f"size({e}) >= {int(s['minProperties'])}")
            if "maxProperties" in s:
                obj.append(f"size({e}) <= {int(s['maxProperties'])}")
            for name, sub in s.get("properties", {}).items():
                obj.append(f"({lit(name)} in {e} ? ({self.schema(sub, f'{e}[{lit(name)}]', depth + 1)}) : true)")
            extra = s.get("additionalProperties", True)
            if extra is False:
                obj.append(f"{e}.all(k{depth}, k{depth} in {lit(sorted(s.get('properties', {})))})")
            elif extra is not True:
                k = f"k{depth}"
                obj.append(f"{e}.all({k}, {k} in {lit(sorted(s.get('properties', {})))} ? true : "
                           f"({self.schema(extra, f'{e}[{k}]', depth + 1)}))")
            if "propertyNames" in s:                 # every key of the object follows the key schema (keys are text)
                kn = f"n{depth}"
                ks = self.schema({"type": "string", **self.resolve(s["propertyNames"])}, kn, depth + 1) or "true"
                obj.append(f"{e}.all({kn}, {ks})")
            parts.append(f"(type({e}) == map ? ({' && '.join(obj) or 'true'}) : false)")
        elif t == "array":
            v, arr = f"x{depth}", []
            if "items" in s:
                arr.append(f"{e}.all({v}, {self.schema(s['items'], v, depth + 1)})")
            if "minItems" in s:
                arr.append(f"size({e}) >= {int(s['minItems'])}")
            if "maxItems" in s:
                arr.append(f"size({e}) <= {int(s['maxItems'])}")
            if s.get("uniqueItems"):
                u, w = f"u{depth}", f"w{depth}"
                arr.append(f"{e}.all({u}, {e}.filter({w}, {w} == {u}).size() == 1)")
            parts.append(f"(type({e}) == list ? ({' && '.join(arr) or 'true'}) : false)")
        elif t == "string":
            parts.append(f"type({e}) == string")
            if s.get("format") == "date-time":
                parts.append(f"{e}.matches({lit(DATE_TIME)})")
            if "minLength" in s:
                parts.append(f"size({e}) >= {int(s['minLength'])}")
            if "maxLength" in s:
                parts.append(f"size({e}) <= {int(s['maxLength'])}")
            if "pattern" in s:                      # JSON Schema patterns search the text, as CEL matches() does
                parts.append(f"{e}.matches({lit(s['pattern'])})")
        elif t == "integer":                         # integers the expressions hold are 64-bit: a larger one does not pass
            parts.append(f"(type({e}) == int || type({e}) == uint || (type({e}) == double && {e} == double(int({e}))))")
            if s.get("format") in INT_RANGE:
                lo, hi = INT_RANGE[s["format"]]
                parts.append(f"double({e}) >= {float(lo)!r} && double({e}) <= {float(hi)!r}")
        elif t == "number":
            parts.append(f"(type({e}) == int || type({e}) == uint || type({e}) == double)")
        if t in ("integer", "number"):
            for key, op in (("minimum", ">="), ("maximum", "<="), ("exclusiveMinimum", ">"), ("exclusiveMaximum", "<")):
                if key in s:
                    parts.append(f"double({e}) {op} {float(s[key])!r}")
            if "multipleOf" in s:            # a whole number of steps: the quotient has no fraction
                m = float(s["multipleOf"])
                parts.append(f"double({e}) / {m!r} == double(int(double({e}) / {m!r}))")
        if t == "boolean":
            parts.append(f"type({e}) == bool")
        elif t == "null":                    # Zendesk's document writes `type: null` (not OpenAPI 3.0): the value is null
            parts.append(f"{e} == null")
        elif t not in (None, "object", "array", "string", "integer", "number"):
            raise ValueError(f"schema type not compiled: {t}")
        if "enum" in s:
            parts.append(f"{e} in {lit(s['enum'])}")
        if "const" in s:
            parts.append(f"{e} == {lit(s['const'])}")
        return " && ".join(parts) if parts else "true"

    def alternatives(self, s, e, depth, compile_one):
        """`anyOf`: one alternative holds; `oneOf`: exactly one holds. Keys beside them (a description) say nothing.
        Keys that would constrain the value beside the alternatives stop the compile."""
        for key in ("anyOf", "oneOf"):
            if key in s:
                beside = set(s) - {key, "x-stripeBypassValidation", "nullable"} - NOTES
                subs = [f"({compile_one(x, e, depth + 1)})" for x in s[key]]
                if key == "anyOf":
                    alt = "(" + " || ".join(subs) + ")"
                else:
                    alt = "([" + ", ".join(subs) + "].filter(b, b).size() == 1)"
                if beside:          # keys that constrain beside the alternatives (GitHub: `type` with `oneOf`): both hold
                    rest = {k: v for k, v in s.items() if k != key}
                    return f"(({compile_one(rest, e, depth + 1)}) && {alt})"
                return alt
        return ""

    def form(self, s, e, depth=0):
        """CEL that is true when `e`, a value read from a form encoding (`a[b][0]=x`), follows the schema `s`. Every
        leaf arrives as text: an integer is digits with an optional sign inside 64 bits, a number is decimal
        text, a boolean is `true` or `false`, an enum is compared as text. Objects and arrays are what the brackets
        built. Each step that reads inside a value is guarded by the conditional operator (`x in e ? ... : true`,
        `type(e) == map ? ... : false`), so nothing is read inside a value that is not there or not of that kind."""
        s = self.resolve(s)
        unknown = self.unknown(s)
        if unknown:
            raise ValueError(f"schema construct not compiled: {sorted(unknown)}")
        both = self.all_of(s, e, depth, self.form)
        if both:
            return both
        alts = self.alternatives(s, e, depth, self.form)
        if alts:
            return alts
        t, inner = s.get("type"), []
        if t == "object" or (t is None and ("properties" in s or "required" in s)):
            for r in self.wanted(s):
                if self.closed:     # an empty value unsets a field (Stripe): a required field left empty is missing
                    inner.append(f"({lit(r)} in {e} ? !(type({e}[{lit(r)}]) == string && {e}[{lit(r)}] == \"\") : false)")
                else:
                    inner.append(f"{lit(r)} in {e}")
            for name, sub in s.get("properties", {}).items():
                inner.append(f"({lit(name)} in {e} ? ({self.form(sub, f'{e}[{lit(name)}]', depth + 1)}) : true)")
            extra = s.get("additionalProperties", True)
            k = f"k{depth}"
            listed = lit(sorted(s.get("properties", {})))
            if extra is False or ("properties" in s and "additionalProperties" not in s):
                # a form names its fields: a field the schema does not list is not taken (the document lists them all)
                inner.append(f"{e}.all({k}, {k} in {listed})")
            elif extra is not True:     # a free key (metadata): an empty value unsets that key
                free = self.form(extra, f'{e}[{k}]', depth + 1)
                if self.closed:
                    free = f"(type({e}[{k}]) == string && {e}[{k}] == \"\") ? true : ({free})"
                inner.append(f"{e}.all({k}, {k} in {listed} ? true : ({free}))")
            return f"(type({e}) == map ? ({' && '.join(inner) or 'true'}) : false)"
        if t == "array":
            v = f"x{depth}"
            if "items" in s:
                inner.append(f"{e}.all({v}, {self.form(s['items'], v, depth + 1)})")
            if "minItems" in s:
                inner.append(f"size({e}) >= {int(s['minItems'])}")
            if "maxItems" in s:
                inner.append(f"size({e}) <= {int(s['maxItems'])}")
            return f"(type({e}) == list ? ({' && '.join(inner) or 'true'}) : false)"
        if t == "string":
            if self.closed and "" not in s.get("enum", []):     # closed (Stripe): an empty value only where the document lists it
                inner.append(f"{e} != \"\"")
            if s.get("format") == "date-time":
                inner.append(f"{e}.matches({lit(DATE_TIME)})")
            if s.get("format") == "decimal":
                inner.append(f"{e}.matches({lit(DECIMAL)})")
            if "minLength" in s:
                inner.append(f"size({e}) >= {int(s['minLength'])}")
            if "maxLength" in s:
                inner.append(f"size({e}) <= {int(s['maxLength'])}")
            if "pattern" in s:
                inner.append(f"{e}.matches({lit(s['pattern'])})")
        elif t == "integer":                    # a number of more than 64 bits cannot be evaluated: it does not pass
            lo, hi = INT_RANGE.get(s.get("format"), INT_RANGE["int64"])
            inner.append(f"({e}.matches({lit('^[+-]?[0-9]+$')}) ? (int({e}) >= {lo} && int({e}) <= {hi}) : false)")
            if self.closed and s.get("format") == "unix-time":    # round 3: a timestamp does not take -0 (Stripe)
                inner.append(f"!{e}.matches({lit('^-0+$')})")
        elif t == "number":
            inner.append(f"{e}.matches({lit(DECIMAL)})")
        elif t == "boolean":
            inner.append(f"{e} in [\"true\", \"false\"]")
        elif t == "null":                       # a form or query value is text, never null: this alternative takes nothing
            inner.append("false")
        elif t is not None:
            raise ValueError(f"schema type not compiled: {t}")
        if t in ("integer", "number"):
            bounds = [f"double({e}) {op} {float(s[key])!r}" for key, op in (("minimum", ">="), ("maximum", "<="),
                      ("exclusiveMinimum", ">"), ("exclusiveMaximum", "<")) if key in s]
            if bounds:
                inner[-1] = f"({inner[-1]} ? ({' && '.join(bounds)}) : false)"
        if "enum" in s:
            inner.append(f"{e} in {lit([v if isinstance(v, str) else json.dumps(v) for v in s['enum']])}")
        if "const" in s:
            inner.append(f"{e} == {lit(s['const'] if isinstance(s['const'], str) else json.dumps(s['const']))}")
        if t is None:
            return " && ".join(inner) or "true"
        return f"(type({e}) == string ? ({' && '.join(inner) or 'true'}) : false)"

    def text_param(self, s, e):
        """CEL for a parameter that arrives as text (path, query, header)."""
        s = self.resolve(s)
        unknown = self.unknown(s, ("multipleOf",))
        if unknown:
            raise ValueError(f"parameter schema construct not compiled: {sorted(unknown)}")
        t = s.get("type")
        if t == "array":
            each, one = self.text_param(s.get("items", {}), "y"), self.text_param(s.get("items", {}), e)
            return f"(type({e}) == list ? {e}.all(y, {each}) : ({one}))"
        parts = [f"type({e}) == string"]
        if t == "integer":
            parts.append(f"{e}.matches({lit('^[+-]?[0-9]+$')})")
            if self.closed and s.get("format") == "unix-time":    # round 3: a timestamp does not take -0 (Stripe)
                parts.append(f"!{e}.matches({lit('^-0+$')})")
            if s.get("format") in INT_RANGE or self.closed:     # closed: an integer is 64 bits, as the server reads it
                lo, hi = INT_RANGE.get(s.get("format"), INT_RANGE["int64"])
                parts.append(f"int({e}) >= {lo} && int({e}) <= {hi}")
        elif t == "number":
            parts.append(f"{e}.matches({lit('^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$')})")
        elif t == "boolean":
            parts.append(f"{e} in [\"true\", \"false\"]")
        elif t not in (None, "string"):
            raise ValueError(f"parameter type not compiled: {t}")
        if "multipleOf" in s:                       # a whole number of steps: the quotient has no fraction
            if t not in ("integer", "number"):
                raise ValueError(f"parameter schema construct not compiled: multipleOf on {t}")
            m = float(s["multipleOf"])
            parts.append(f"double({e}) / {m!r} == double(int(double({e}) / {m!r}))")
        if t in (None, "string"):
            if self.closed and "" not in [str(x) for x in s.get("enum", [])]:   # round 3: "" only where listed
                parts.append(f"{e} != \"\"")
            if "minLength" in s:
                parts.append(f"size({e}) >= {int(s['minLength'])}")
            if "maxLength" in s:
                parts.append(f"size({e}) <= {int(s['maxLength'])}")
            if "pattern" in s:
                parts.append(f"{e}.matches({lit(s['pattern'])})")
        if "enum" in s:
            parts.append(f"{e} in {lit([str(x) for x in s['enum']])}")
        return " && ".join(parts)

    def security(self, reqs):
        """CEL for the operation's security: one of the alternatives, each with all its schemes. An API key must be
        there in its place; HTTP bearer, OAuth 2 and OpenID Connect need an Authorization header (the token itself is
        checked by whoever issued it, not here)."""
        if not reqs:
            return ""
        schemes = self.doc.get("components", {}).get("securitySchemes", {})
        alts = []
        for alt in reqs:
            conds = []
            for name in alt:
                sc = schemes[name]
                if sc["type"] == "apiKey":
                    where = {"header": "args.header", "query": "args.query"}.get(sc["in"])
                    if where is None:
                        raise ValueError(f"API key in {sc['in']} not compiled")
                    key = sc["name"].lower() if sc["in"] == "header" else sc["name"]
                    conds.append(f"{lit(key)} in {where}")
                elif sc["type"] in ("http", "oauth2", "openIdConnect"):
                    conds.append('"authorization" in args.header')
                else:
                    raise ValueError(f"security scheme {sc['type']} not compiled")
            alts.append("(" + (" && ".join(conds) or "true") + ")")
        return " || ".join(alts)

    def table(self, base=""):
        doors, routes = {}, []
        loc = {"path": "path", "query": "query", "header": "header"}
        for path, ops in self.doc["paths"].items():
            shared = [self.resolve(x) for x in ops.get("parameters", [])]
            for method, op in ops.items():
                if method not in ("get", "put", "post", "delete", "patch", "head", "options"):
                    continue
                door = op.get("operationId") or f"{method} {path}"
                try:
                    req = self.operation(door, op, shared, loc)
                except NotReadable as why:          # the door stays in the menu, closed, with the reason
                    doors[door] = {"form": {"path": "object", "query": "object", "header": "object", "body": "object"},
                                   "closed": f"{why}: the table does not read this operation"}
                else:
                    doors[door] = {"form": {"path": "object", "query": "object", "header": "object", "body": "object"},
                                   "requires": req}
                multi = {p["name"] for p in shared + [self.resolve(x) for x in op.get("parameters", [])]
                         if p["in"] == "path" and (p.get("x-multi-segment") or self.resolve(p.get("schema", {})).get("x-multi-segment"))}
                # a path parameter over several segments (a branch `feat/x`, a file path) is written `{name+}`
                routes.append({"method": method, "path": "/".join(f"{{{x[1:-1]}+}}" if x[1:-1] in multi else x
                                                                   for x in path.split("/")), "door": door})
        return {"table": self.doc.get("info", {}).get("title", "openapi"), "doors": doors,
                "http": {"base": base, "routes": routes}}

    def operation(self, door, op, shared, loc):
        """The conditions of one operation's door."""
        declared = self.doc.get("components", {}).get("securitySchemes", {})
        for alt in op.get("security", self.doc.get("security")) or []:
            for scheme in alt:
                if scheme not in declared:
                    raise NotReadable(f"the security scheme {scheme} is used and not declared by the document")
        req = []
        for p in shared + [self.resolve(x) for x in op.get("parameters", [])]:
            if p["in"] not in loc:
                raise ValueError(f"{door}: parameter in {p['in']} not compiled")
            name = p["name"].lower() if p["in"] == "header" else p["name"]
            e = f"args.{loc[p['in']]}[{lit(name)}]"
            where = f"args.{loc[p['in']]}"
            sch = self.resolve(p.get("schema", {}))
            if p.get("required") and "default" not in sch:   # with a default, the server uses it when absent
                req.append({"if": "expr", "expr": f"{lit(name)} in {where}",
                            "else": f"the {p['in']} parameter {p['name']} is required"})
            if p["in"] == "query" and self.closed:     # closed (Stripe): an empty query value is not given
                # round 3: Stripe reads an empty value as not given for `limit` only; any other is read as written
                where_given = (f"{lit(name)} in {where} && !(type({e}) == string && {e} == \"\")" if name == "limit"
                               else f"{lit(name)} in {where}")
            else:
                where_given = f"{lit(name)} in {where}"
            if p["in"] == "query" and not p.get("allowEmptyValue") and not self.closed:
                req.append({"if": "expr", "expr": f"!({lit(name)} in {where}) || type({e}) != string || {e} != \"\"",
                            "else": f"the query parameter {p['name']} is empty"})
            if p.get("style") == "deepObject" or "anyOf" in sch or "oneOf" in sch or sch.get("type") == "object":
                # brackets in the name (`created[gt]`, `expand[]`), read as a form; guarded by `? :`
                expr = f"{where_given} ? ({self.form(sch, e)}) : true"
            else:
                cond = self.text_param(p.get("schema", {}), e)
                expr = f"{where_given} ? ({cond}) : true" if self.closed else f"!({where_given}) || ({cond})"
            req.append({"if": "expr", "expr": expr,
                        "else": f"the {p['in']} parameter {p['name']} is not as the document states"})
        rb = op.get("requestBody")
        if rb:
            rb = self.resolve(rb) if "$ref" in rb else rb
            js = (rb.get("content") or {}).get("application/json")
            fm = (rb.get("content") or {}).get("application/x-www-form-urlencoded")
            if rb.get("required"):
                req.append({"if": "expr", "expr": "args.body.present", "else": "this operation needs a body"})
            if fm is not None and js is None:   # a form body, read by reader_http into the structure it names
                req.append({"if": "expr", "expr": "!args.body.present || !(\"unread\" in args.body)",
                            "else": "the form body is not written as a form the system reads"})
                req.append({"if": "expr", "expr": f"args.body.present ? ({self.form(fm.get('schema', {}), 'args.body.value')}) : true",
                            "else": "the body does not follow the document's schema"})
            elif js is not None:
                req.append({"if": "expr", "expr": f"args.body.present ? ({self.schema(js.get('schema', {}), 'args.body.value')}) : true",
                            "else": "the body does not follow the document's schema"})
            else:                               # the gate reads JSON bodies only: another media type is not taken
                req.append({"if": "expr", "expr": "!args.body.present", "else": "this operation takes no JSON body"})
        # an operation with no request body does not read one: a body sent to it changes nothing
        sec = self.security(op.get("security", self.doc.get("security")))
        if sec:
            req.insert(0, {"if": "expr", "expr": sec, "else": "the credentials this operation needs are not there"})
        if self.closed:
            names = sorted({p["name"] for p in shared + [self.resolve(x) for x in op.get("parameters", [])] if p["in"] == "query"})
            req.insert(0, {"if": "expr", "expr": f"args.query.all(q, q in {lit(names)})",
                           "else": "a query parameter the operation does not declare"})
        return req


def main():
    closed = "--closed" in sys.argv
    argv = [a for a in sys.argv if a != "--closed"]
    src, out = argv[1], argv[2]
    base = argv[3] if len(argv) > 3 else ""
    text = open(src).read()
    if src.endswith(".json"):
        doc = json.loads(text)
    else:
        import yaml
        doc = yaml.safe_load(text)
    t = Compiler(doc, closed).table(base)
    json.dump(t, open(out, "w"), indent=1)
    print(len(t["doors"]), "doors")


if __name__ == "__main__":
    main()
