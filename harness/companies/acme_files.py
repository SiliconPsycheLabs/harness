"""Acme Components as a file tree (`harness/world.py`): the company of the document skills."""
from harness import world

READ, WRITE, REGISTER = world.READ, world.WRITE, {}


def build(root, key):
    world.build(root)
    return root


def finish(handle, row, task):
    return {}
