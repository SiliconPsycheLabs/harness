"""The document search tools: search a folder, read a document, save an answer with its sources. Fixed programs."""
import json
import os
import re


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def _log(root, path):
    os.makedirs(os.path.join(str(root), "_log"), exist_ok=True)
    with open(os.path.join(str(root), "_log", "reads.txt"), "a") as f:
        f.write(os.path.normpath("/" + str(path).lstrip("/")) + "\n")


LIBRARY = ["/acme/contracts", "/acme/documents/policies"]


def _documents(root, folders):
    for folder in folders:
        base = real(root, folder)
        for d, _, files in os.walk(base):
            for f in sorted(files):
                if f.endswith(".txt"):
                    text = open(os.path.join(d, f), encoding="utf-8").read()
                    yield "/" + os.path.relpath(os.path.join(d, f), str(root)), text


def search_documents(root, query, folder=None):
    if folder and not os.path.isdir(real(root, folder)):
        raise ValueError(f"no folder at {folder}")
    if folder:
        _log(root, folder)
    docs = list(_documents(root, [folder] if folder else LIBRARY))
    words = [w.casefold() for w in re.findall(r"\w+", query) if len(w) > 2]
    hits = []
    for path, text in docs:
        title = text.split("\n")[0].strip()
        score = sum(2 if w in (title + " " + path).casefold() else 1 for w in words if w in (text + " " + path).casefold())
        if score:
            line = next((ln for ln in text.split("\n")[1:] if any(w in ln.casefold() for w in words)), "")
            hits.append((-score, path, title, line.strip()[:160]))
    hits.sort()
    if hits:
        return json.dumps([{"path": p, "title": t, "line": ln} for _, p, t, ln in hits[:5]], ensure_ascii=False)
    return "no document holds those words. The documents there are: " + json.dumps([{"path": p, "title": t.split("\n")[0].strip()} for p, t in docs], ensure_ascii=False)


def read_document(root, path):
    full = real(root, path)
    if not os.path.isfile(full):
        raise ValueError(f"no document at {path}")
    _log(root, path)
    return open(full, encoding="utf-8").read()


def save_answer(root, path, question, answer, source):
    sources = [source]
    for s in sources:
        if not os.path.isfile(real(root, s)):
            raise ValueError(f"the source {s} is not a document: give the path of the document you read")
    target = real(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump({"question": question, "answer": answer, "sources": [os.path.normpath("/" + str(s).lstrip("/")) for s in sources]}, f, ensure_ascii=False, indent=1)
    return f"saved {os.path.normpath('/' + str(path).lstrip('/'))} with {len(sources)} source(s)"
