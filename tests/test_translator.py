import pytest

from office_translate import ConfigError, ModelError, Translator, translate_text


def make(opts, **kw):
    return Translator("German", **{**opts, **kw})


def test_translate_text_string(opts):
    assert translate_text("hello world", target_lang="German", **opts) == "HELLO WORLD"


def test_whitespace_and_order(opts):
    t = make(opts)
    assert t.translate(["  one ", "two\n", "", "  "]) == ["  ONE ", "TWO\n", "", "  "]


def test_skips_text_without_letters(server, opts):
    assert make(opts).translate(["123", "4.5 %", "--"]) == ["123", "4.5 %", "--"]
    assert server.requests == []


def test_dedupe(server, opts):
    assert make(opts).translate(["same", "same", "other"]) == ["SAME", "SAME", "OTHER"]
    content = server.user_messages()[0]
    assert content.count("same") == 1


def test_batch_size(server, opts):
    texts = [f"text {i}" for i in range(7)]
    result = make(opts, batch_size=3, concurrency=1).translate(texts)
    assert result == [t.upper() for t in texts]
    assert len(server.requests) == 3


def test_batch_chars(server, opts):
    texts = ["a" * 30, "b" * 30, "c" * 30]
    make(opts, batch_chars=50).translate(texts)
    assert len(server.requests) == 3


def test_length_splits_batch(server, opts):
    server.mode = "length"
    texts = ["one", "two", "three", "four"]
    assert make(opts).translate(texts) == ["ONE", "TWO", "THREE", "FOUR"]
    assert len(server.requests) > 1


def test_missing_items_are_retried(server, opts):
    server.mode = "skip_items"
    assert make(opts).translate(["one", "two", "three"]) == ["ONE", "TWO", "THREE"]
    assert len(server.requests) == 2


def test_server_error(server, opts):
    server.mode = "fail"
    with pytest.raises(ModelError, match="failed"):
        make(opts).translate(["hello"])


def test_prompt_languages_and_instructions(server, opts):
    Translator("French", "English", instructions="Use a formal tone.", **opts).translate(["hello"])
    system = server.system_messages()[0]
    assert "from English into French" in system
    assert "Use a formal tone." in system


def test_glossary_in_prompt(server, opts):
    server.replace = {"invoice": "Rechnungen"}
    t = make(opts, glossary={"invoice": "Rechnung"})
    assert t.translate(["Send the invoice today"]) == ["SEND THE Rechnungen TODAY"]
    assert "invoice" in server.user_messages()[0]
    assert "'invoice' -> 'Rechnung'" in server.system_messages()[0]
    assert "Inflect" in server.system_messages()[0]
    assert len(server.requests) == 1


def test_glossary_retry_then_success(server, opts, caplog):
    server.replace = {"invoice": "Rechnung"}
    server.replace_from = 1
    t = make(opts, glossary={"invoice": "Rechnung"})
    assert t.translate(["Send the invoice today", "hello"]) == ["SEND THE Rechnung TODAY", "HELLO"]
    assert len(server.requests) == 2
    assert "did not use" in server.system_messages()[1]
    assert "HELLO" not in server.user_messages()[1].upper()
    assert "not used" not in caplog.text


def test_glossary_warning_when_missing(server, opts, caplog):
    t = make(opts, glossary={"invoice": "Rechnung"})
    assert t.translate(["Send the invoice today"]) == ["SEND THE INVOICE TODAY"]
    assert len(server.requests) == 2
    assert "'invoice' -> 'Rechnung' not used" in caplog.text


def test_strict_glossary(server, opts):
    t = make(opts, glossary={"invoice": "Rechnung"}, strict_glossary=True)
    assert t.translate(["Send the invoice today"]) == ["SEND THE Rechnung TODAY"]
    assert "__GLOSSARY_0__" in server.user_messages()[0]
    assert "Rechnung" in server.system_messages()[0]
    assert len(server.requests) == 1


def test_glossary_empty_target_uses_token(server, opts):
    t = make(opts, glossary={"Acme Cloud": ""})
    assert t.translate(["Open Acme Cloud now"]) == ["OPEN Acme Cloud NOW"]
    assert "__GLOSSARY_0__" in server.user_messages()[0]
    assert len(server.requests) == 1


def test_no_glossary_lines_without_match(server, opts):
    make(opts, glossary={"invoice": "Rechnung"}).translate(["nothing here"])
    assert "GLOSSARY" not in server.system_messages()[0]


def test_api_key_header(server, opts):
    make(opts, api_key="secret").translate(["hello"])
    assert server.requests[0]["headers"]["authorization"] == "Bearer secret"


def test_no_api_key(server, opts):
    make(opts).translate(["hello"])
    assert server.requests[0]["headers"]["authorization"] == "Bearer not-needed"


def test_target_required(opts):
    with pytest.raises(ConfigError, match="target_lang"):
        Translator(" ", **opts)


def test_missing_config():
    with pytest.raises(ConfigError, match="base_url"):
        Translator("German")
