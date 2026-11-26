"""A skill folder, loaded. Software, holds no rule."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Skill:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.spec = json.loads((self.folder / "skill.json").read_text())
        self.name = self.spec["name"]
        self.version = self.spec["version"]
        self.tools = self.spec["tools"]                       # as an MCP server lists them: name, description, inputSchema
        self.languages = self.spec.get("languages", {})       # which field of which tool is a path, an address ...
        self.prompt = self.spec["prompt"]
        self._tool = _module(self.folder / "tool.py", f"harness_skill_{self.name}_tool")
        self._check = _module(self.folder / "check.py", f"harness_skill_{self.name}_check")

    def tasks(self):
        return json.loads((self.folder / "tasks.json").read_text())

    def run(self, tool, args, root):
        """Run one tool of the skill inside `root` (the company's file tree for this run): the text the model reads."""
        return getattr(self._tool, tool)(root, **args)

    def check(self, task, root):
        return self._check.check(task, root)

    def golden(self, task):
        return self._check.golden(task)


def load(name):
    return Skill(HERE / "skills" / name)
