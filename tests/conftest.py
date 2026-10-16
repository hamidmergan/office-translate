import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

ITEM = re.compile(r'<s id="(\d+)">(.*?)</s>', re.DOTALL)
TAG = re.compile(r"(<[^>]+>)")


def fake_translate(text: str) -> str:
    """Upper-case everything outside of tags, so the result is easy to check."""
    return "".join(part if TAG.fullmatch(part) else part.upper() for part in TAG.split(text))


class FakeServer:
    def __init__(self):
        self.requests = []
        self.mode = None
        # Words to swap in replies from request number replace_from on, e.g. {"invoice": "Rechnungen"}.
        self.replace = {}
        self.replace_from = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                outer.requests.append({"headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
                if outer.mode == "fail":
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"{}")
                    return
                items = ITEM.findall(body["messages"][1]["content"])
                finish = "stop"
                if outer.mode == "length" and len(items) > 1:
                    finish = "length"
                    items = items[:1]
                if outer.mode == "skip_items" and len(items) > 1:
                    items = items[:-1]
                parts = []
                for number, text in items:
                    new = fake_translate(text)
                    if len(outer.requests) > outer.replace_from:
                        for old, word in outer.replace.items():
                            new = re.sub(re.escape(old), word, new, flags=re.IGNORECASE)
                    if outer.mode == "drop_tags":
                        new = re.sub(r"</?g\d+>", "", new)
                    parts.append(f'<s id="{number}">{new}</s>')
                payload = {
                    "id": "x",
                    "object": "chat.completion",
                    "created": 0,
                    "model": body["model"],
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": finish,
                            "message": {"role": "assistant", "content": "\n".join(parts)},
                        }
                    ],
                }
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.httpd.server_port}/v1"

    def user_messages(self):
        return [r["body"]["messages"][1]["content"] for r in self.requests]

    def system_messages(self):
        return [r["body"]["messages"][0]["content"] for r in self.requests]

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    s = FakeServer()
    yield s
    s.stop()


@pytest.fixture
def opts(server):
    return {"base_url": server.base_url, "model": "test-model", "max_retries": 0}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith("OFFICE_TRANSLATE_") or name == "OPENAI_API_KEY":
            monkeypatch.delenv(name)
