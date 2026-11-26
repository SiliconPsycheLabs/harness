"""A company is where a skill does its work: a file tree, or a real application with invented data.

Every company module gives: `READ`, `WRITE` (folders the company opens to path fields), `REGISTER` (the company's own
lists a rule may read, e.g. its suppliers), `build(root, key)` (the company at its start for one run: what the tools
and the check are handed), and `finish(handle, row, task)` (keep the evidence, give the run's resources back).
"""
import importlib


def load(name):
    return importlib.import_module(f"harness.companies.{name}")
