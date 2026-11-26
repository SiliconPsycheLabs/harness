"""Where the model answers from. A backend is a function: the body of a chat completion in, the answer out."""
import time


def openai_compatible(base_url, api_key, model, extra=None):
    """Any OpenAI-compatible server (vLLM, a provider): the customer's own model in production."""
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=300)

    def chat(body):
        body = dict(body)
        extra_body = {k: body.pop(k) for k in list(body) if k in ("chat_template_kwargs",)}
        extra_body.update(extra or {})
        return client.chat.completions.create(model=model, extra_body=extra_body or None, **body).model_dump()
    chat.model = model
    return chat


def local(base_url, model):
    """A server on the same machine (vLLM on a card of ours), called with the standard library: no client to install.
    HARNESS_API_KEY, when set, is sent as the bearer token."""
    import json
    import os
    import urllib.request
    headers = {"Content-Type": "application/json"}
    if os.environ.get("HARNESS_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["HARNESS_API_KEY"]

    def chat(body):
        body = {"model": model, "chat_template_kwargs": {"enable_thinking": False}, **body}
        last = ""
        for wait in [0, 20, 60, 120, 120]:
            time.sleep(wait)
            try:
                req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", json.dumps(body).encode(), headers)
                with urllib.request.urlopen(req, timeout=600) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as x:
                last = f"{x.code}: {x.read()[:200]!r}"
                if x.code < 500:
                    break
            except Exception as x:  # noqa: BLE001  the server restarting under a run is waited out
                last = f"{type(x).__name__}: {x}"
        raise RuntimeError(f"local server: {last}")
    chat.model = model
    return chat
