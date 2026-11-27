# Harness: agents that do office work behind a deterministic gate

A deterministic gate decides what an agent may do: every action passes or it does not, with rules that are a table
and nothing probabilistic in the decision ([the gate](https://github.com/SiliconPsycheLabs/gate)). This repository is
the other half: what makes the agent do the work, on a model you own, with that gate in front of every action, and
the count of what came out right and what was stopped. Built by [Silicon Psyche Labs](https://splabs.io).

The results of every skill, request by request, are public: [harness-results](https://github.com/SiliconPsycheLabs/harness-results).

## A skill

One skill is one thing an office needs done. It is a folder in `harness/skills/`:

| File | What it holds |
| --- | --- |
| `skill.json` | the tools as an MCP server would list them (name, description, input schema), the instructions the model gets, the company's limits on the tools, and the skill's public texts |
| `tool.py` | a program that does the work: the model fills the fields, the program does the same thing every time |
| `tasks.json` | requests, each with what the result must hold, plus requests the company's limits must stop |
| `check.py` | reads the result apart from the model and from the gate; `golden(task)` is the call a correct agent would make |

The rules of a skill are not written by hand. `harness/gatebox.py` compiles one tool of the table per tool of the
skill from the tool's own input schema (`harness/tablec/`), then adds the company's limits: a tool closed with its
reason, a field that must be one of a list of the company, a condition on the arguments, the folders a path may touch.
A new skill therefore arrives with its rules.

Two more things a skill can say in its `skill.json`:

- **An action waits for a person** (`limits.held`): the tool's call is held with a fixed reason until a person of the
  named role opens that exact call, once. In a test the person is the skill's `check.confirms(task, tool, args,
  company)`, a program; in production it is whoever answers the gate's question. `payments` holds every payment this
  way, after a deterministic check that the bank account is the one on file for the supplier.
- **A job made of several skills** (`uses`): a skill with no tool of its own takes named tools of other skills, each
  with the rules it already had. `accounts_payable` is one agent that reads the invoice (`pdf`), enters it
  (`supplier_bill`) and writes to the supplier (`mail`).
- **A database behind the gate** (`limits.database`): the tables, their columns and which of them may be read or
  changed. The gate reads the SQL statement itself before it runs, so a closed column does not pass inside a sort or
  a subquery either.
- **What makes a small model finish** (`must_act`, `must_call`): one fixed line, once, when a job is answered with no
  tool called, or ended before the tool that makes its result was called. The card counts how often.

| Skill | Where it works | Tools |
| --- | --- | --- |
| `word` | the company's file tree | `write_docx` |
| `excel` | the company's file tree | `write_xlsx` |
| `pdf` | the company's file tree | `read_pdf`, `save_record` |
| `mail` | the company's file tree and an outbox | `find_contact`, `send_mail` |
| `supplier_bill` | a real accounting application (Odoo 17, invented data) | `find_supplier`, `create_supplier_bill`, `create_supplier`, `set_supplier_bank` |
| `powerpoint` | the company's file tree | `write_pptx` |
| `calendar` | the company calendar | `find_person`, `find_free_slots`, `create_event` |
| `filing` | the company's file tree | `list_folder`, `copy_file`, `move_file` |
| `doc_search` | the company's contracts and policies | `search_documents`, `read_document`, `save_answer` |
| `database` | the company's sales database (SQLite), behind the gate's SQL reader | `describe_database`, `run_query`, `save_answer` |
| `payments` | the same accounting application | `list_open_bills`, `pay_bill` (held for a person) |
| `credit_control` | the accounting application and an outbox | `list_overdue_invoices`, `send_reminder`, `write_off_invoice`, `extend_due_date` |
| `accounts_payable` | the file tree and the accounting application together | the tools of `pdf`, `supplier_bill` and `mail` |

## Run one

```
pip install "git+https://github.com/SiliconPsycheLabs/harness"

python -m harness.run golden word                      # scripted calls, no model: the tool, the check and the rules agree

export HARNESS_BASE_URL=http://localhost:8000/v1       # any OpenAI-compatible server (vLLM, a provider)
export HARNESS_MODEL=<the model's name>
export HARNESS_MODE=json                               # one JSON object per step the server is made to follow; `tools` for the server's own tool calling
python -m harness.run run     word out/word.jsonl      # every request in two arms; rows written one by one
python -m harness.run measure word out/word.jsonl      # the counts and the card (out/word.jsonl.card.json)
```

Two arms. `enforce`: a call that does not pass the gate does not run, and the model reads the gate's fixed reason.
`shadow`: the gate's answer is recorded and every call runs, so the run shows what the agent does with no gate.

The card of a run holds the recipe (skill and harness version, model, the table and its hash, the instructions) and
the count: requests done right, forbidden requests done, forbidden actions nobody asked for, calls passed and stopped,
tokens and seconds per request.

## Requests at scale

`harness/generate.py` makes requests by the thousand. The facts of a request come from a seed, by program (language,
people, numbers, dates, lines, totals, what the limits must stop), so the right answer is known before any model
writes a word. A model only words the colleague's message, and the wording is kept only if every fact is in it by
string match.

```
export HARNESS_GEN_BASE_URL=http://localhost:8000/v1 HARNESS_GEN_MODEL=<a model that writes well>
python -m harness.generate supplier_bill gen/supplier_bill.jsonl 1500
HARNESS_TASKS=gen/supplier_bill.jsonl HARNESS_SLICE=0:150 python -m harness.run run supplier_bill out/bill_b0.jsonl 2
```

## The pieces

| File | What it does |
| --- | --- |
| `harness/loop.py` | the agent loop on an OpenAI-compatible server: every tool call goes to the gate before it runs |
| `harness/gatebox.py` | the table compiled from the skills, each call decided by the gate's action manager, each answer kept as its record |
| `harness/tablec/` | the compiler from a tool's input schema to a tool of the table |
| `harness/companies/` | where a skill works: a file tree (`acme_files`), a real application (`acme_odoo`, set up by `acme_odoo_setup/`) |
| `harness/run.py` | `golden`, `run`, `measure`, `replay` |
| `harness/generate.py` | requests at scale |

## Licence

Apache-2.0. The engine is open; the companies, people and amounts in the requests are invented.

## In plain words

This is the program that lets an AI agent do an office job (write a document, enter an invoice in the accounts) while
fixed rules decide every action before it happens. It comes with ready-made jobs (documents, spreadsheets, reading invoices, mail, entering invoices in the accounts), test requests whose right answer is
known in advance, and a count of how many came out right and how many times the agent was stopped.
