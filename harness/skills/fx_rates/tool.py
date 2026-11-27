"""The outside-service tools: a GET, a POST and the record of a conversion. `http_get` and `http_post` call whatever
address they are given: which address may be called, and whether anything may be sent, is the gate's business."""
import json
import os

from harness import web


def real(root, path):
    return os.path.join(str(root), os.path.normpath("/" + str(path).lstrip("/")).lstrip("/"))


def http_get(root, url):
    st, body = web.get(root, url)
    return f"HTTP {st}\n{body[:1500]}"


def http_post(root, url, body):
    st, text = web.post(root, url, body)
    return f"HTTP {st}\n{text[:500]}"


def save_conversion(root, path, invoice, currency, amount, date, amount_eur, source_url):
    target = real(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump({"invoice": invoice, "currency": currency, "amount": amount, "date": date, "amount_eur": amount_eur, "source_url": source_url}, f, ensure_ascii=False, indent=1)
    return f"saved {os.path.normpath('/' + str(path).lstrip('/'))}: {invoice}, {amount} {currency} = {amount_eur} EUR"
