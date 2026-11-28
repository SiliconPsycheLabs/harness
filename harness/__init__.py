"""The harness: what makes an agent do the work, with the gate in front of every action.

A skill is one thing an office needs done. It is a folder: `skill.json` (the tools with their input schemas, which
field carries a path, the instructions the model gets), `tool.py` (a program of ours that does the work the same way
every time), `tasks.json` (requests with what the result must hold) and `check.py` (reads the result, apart from the
model and from the gate). The table the gate reads is compiled from the tools' own schemas.

    skill.py    load a skill folder
    gatebox.py  the gate around a set of skills: compile the table, decide each call, keep the record
    loop.py     the agent loop on an OpenAI-compatible server: every tool call goes to the gate before it runs
    backends.py where the model answers from: any OpenAI-compatible server
    run.py      golden (no model), run (rows written one by one), measure (the card)
"""

__version__ = "0.1.1"
