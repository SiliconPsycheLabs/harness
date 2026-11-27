"""The web search tools: search an open encyclopedia, read a page, save the answer with its address. `fetch_page`
reads whatever address it is given, as a browser does: which address may be read is the gate's business."""
import json
import os
import urllib.parse

from harness import web


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def search_web(root, query, language):
    host = f"{language}.wikipedia.org"
    st, body = web.get(root, f"https://{host}/w/api.php?action=query&list=search&format=json&srlimit=5&srsearch=" + urllib.parse.quote(query), kind="search")
    if st != 200:
        raise ValueError(f"the search did not answer (HTTP {st}): call it again")
    hits = json.loads(body).get("query", {}).get("search", [])
    out = [{"title": h["title"], "url": f"https://{host}/wiki/" + urllib.parse.quote(h["title"].replace(" ", "_"))} for h in hits]
    return json.dumps(out, ensure_ascii=False) if out else "no page matches those words"


def fetch_page(root, url):
    u = urllib.parse.urlsplit(url)
    if (u.hostname or "").endswith(".wikipedia.org") and u.path.startswith("/wiki/"):      # the page's opening text, as plain text
        title = urllib.parse.unquote(u.path[6:])
        web.log(root, "get", url)
        st, body = web.get(root, f"https://{u.hostname}/w/api.php?action=query&prop=extracts&explaintext=1&exintro=1&redirects=1&format=json&titles=" + urllib.parse.quote(title), kind="read")
        if st != 200:
            raise ValueError(f"the site did not answer (HTTP {st}): call it again")
        pages = json.loads(body).get("query", {}).get("pages", {})
        text = next((p.get("extract", "") for p in pages.values()), "")
        if not text:
            raise ValueError("no such page: use an address exactly as search_web gave it")
        return f"{title.replace('_', ' ')}\n{text[:3000]}"
    st, body = web.get(root, url)
    return f"HTTP {st}\n{web.text_of(body)[:2000]}"


def save_answer(root, path, question, answer, source_url):
    target = real(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump({"question": question, "answer": answer, "source_url": source_url}, f, ensure_ascii=False, indent=1)
    return f"saved {os.path.normpath('/' + str(path).lstrip('/'))}"
