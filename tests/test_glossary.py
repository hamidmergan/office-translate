import json

import pytest

from office_translate import Glossary, GlossaryError, load_glossary


def test_protect_and_restore():
    g = Glossary({"machine learning": "maschinelles Lernen", "machine": "Maschine"})
    text, used = g.protect("Machine learning needs a machine.")
    assert "machine" not in text.lower()
    assert len(used) == 2
    assert g.restore(text) == "maschinelles Lernen needs a Maschine."


def test_word_boundaries():
    g = Glossary({"cat": "Katze"})
    text, used = g.protect("The category of the cat")
    assert text == "The category of the __GLOSSARY_0__"
    assert used == [0]


def test_case_sensitive():
    g = Glossary({"Apple": "Apfel"}, case_sensitive=True)
    assert g.protect("apple")[1] == []
    assert g.protect("Apple")[1] == [0]


def test_restore_damaged_token():
    g = Glossary({"cloud": "Wolke"})
    assert g.restore("_GLOSSARY_0_ and __glossary_0__") == "Wolke and Wolke"


def test_empty_target_keeps_source():
    g = Glossary({"Kubernetes": ""})
    text, _ = g.protect("Run Kubernetes")
    assert g.restore(text) == "Run Kubernetes"


def test_describe():
    g = Glossary({"invoice": "Rechnung"})
    assert "__GLOSSARY_0__" in g.describe([0])
    assert "Rechnung" in g.describe([0])


def test_load_csv_with_header(tmp_path):
    path = tmp_path / "g.csv"
    path.write_text("source,target\ninvoice,Rechnung\n# comment\nsupplier,Lieferant\n", encoding="utf-8")
    g = load_glossary(path)
    assert dict(g.terms) == {"invoice": "Rechnung", "supplier": "Lieferant"}


def test_load_semicolon_csv(tmp_path):
    path = tmp_path / "g.csv"
    path.write_text("invoice;Rechnung\nsupplier;Lieferant\n", encoding="utf-8")
    assert len(load_glossary(path)) == 2


def test_load_tsv(tmp_path):
    path = tmp_path / "g.tsv"
    path.write_text("term\ttranslation\ninvoice, final\tSchlussrechnung\n", encoding="utf-8")
    assert dict(load_glossary(path).terms) == {"invoice, final": "Schlussrechnung"}


def test_load_json_forms(tmp_path):
    a = tmp_path / "a.json"
    a.write_text(json.dumps({"invoice": "Rechnung"}), encoding="utf-8")
    b = tmp_path / "b.json"
    b.write_text(json.dumps([{"source": "invoice", "target": "Rechnung"}, ["tax", "Steuer"]]), encoding="utf-8")
    assert len(load_glossary(a)) == 1
    assert len(load_glossary(b)) == 2


def test_load_errors(tmp_path):
    with pytest.raises(GlossaryError, match="not found"):
        load_glossary(tmp_path / "missing.csv")
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(GlossaryError, match="JSON"):
        load_glossary(bad)
    wide = tmp_path / "wide.csv"
    wide.write_text("a,b,c\n", encoding="utf-8")
    with pytest.raises(GlossaryError, match="more than two"):
        load_glossary(wide)
