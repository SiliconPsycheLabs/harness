"""The filing tools: list a folder, copy a file, move a file. Fixed programs on the company's file tree."""
import os
import shutil


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def _log(root, path):
    os.makedirs(os.path.join(str(root), "_log"), exist_ok=True)
    with open(os.path.join(str(root), "_log", "reads.txt"), "a") as f:
        f.write(os.path.normpath("/" + str(path).lstrip("/")) + "\n")


def _plain(text):
    import re
    import unicodedata
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower())


def list_folder(root, path, name_contains=None):
    full = real(root, path)
    if not os.path.isdir(full):
        raise ValueError(f"no folder at {path}")
    _log(root, path)
    names = sorted(n + ("/" if os.path.isdir(os.path.join(full, n)) else "") for n in os.listdir(full))
    if name_contains:
        names = [n for n in names if _plain(name_contains) in _plain(n)]
        return "\n".join(names) if names else f"no name in the folder contains {name_contains!r}"
    return "\n".join(names) if names else "the folder is empty"


def _put(root, source, destination, move):
    src, dst = real(root, source), real(root, destination)
    if not os.path.isfile(src):
        raise ValueError(f"no file at {source}")
    if os.path.isdir(dst) or str(destination).endswith("/"):
        raise ValueError(f"{destination} is a folder: give the full path of the file, with its name")
    if os.path.exists(dst):
        raise ValueError(f"there is already a file at {destination}")
    _log(root, source)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    (shutil.move if move else shutil.copyfile)(src, dst)
    return f"{'moved' if move else 'copied'} {os.path.normpath('/' + str(source).lstrip('/'))} to {os.path.normpath('/' + str(destination).lstrip('/'))}"


def copy_file(root, source, destination):
    return _put(root, source, destination, False)


def move_file(root, source, destination):
    return _put(root, source, destination, True)
