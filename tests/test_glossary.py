import json

import pytest

from office_translate import Glossary, GlossaryError, load_glossary


def test_protect_keeps_terms_with_target():
    g = Glossary({"machine learning": "maschinelles Lernen", "machine": "Maschine"})
    text, tokens, found = g.protect("Machine learning needs a machine. Machine learning again.")
    assert text == "Machine learning needs a machine. Machine learning again."
    assert tokens == []
    assert found == [0, 1]


def test_strict_protect_and_restore():
    g = Glossary({"machine learning": "maschinelles Lernen", "machine": "Maschine"})
    text, tokens, found = g.protect("Machine learning needs a machine.", strict=True)
    assert "machine" not in text.lower()
    assert len(tokens) == 2
    assert found == []
    assert g.restore(text) == "maschinelles Lernen needs a Maschine."


def test_word_boundaries():
    g = Glossary({"cat": "Katze"})
    text, tokens, _ = g.protect("The category of the cat", strict=True)
    assert text == "The category of the __GLOSSARY_0__"
    assert tokens == [0]
    assert g.protect("The category")[2] == []


def test_case_sensitive():
    g = Glossary({"Apple": "Apfel"}, case_sensitive=True)
    assert g.protect("apple")[2] == []
    assert g.protect("Apple")[2] == [0]


def test_restore_damaged_token():
    g = Glossary({"cloud": "Wolke"})
    assert g.restore("_GLOSSARY_0_ and __glossary_0__") == "Wolke and Wolke"


def test_empty_target_keeps_source():
    g = Glossary({"Kubernetes": ""})
    text, tokens, found = g.protect("Run Kubernetes")
    assert text == "Run __GLOSSARY_0__"
    assert tokens == [0]
    assert found == []
    assert g.restore(text) == "Run Kubernetes"


def test_describe():
    g = Glossary({"invoice": "Rechnung"})
    assert "__GLOSSARY_0__" in g.describe([0])
    assert "Rechnung" in g.describe([0])


def test_describe_terms():
    g = Glossary({"invoice": "Rechnung", "machine learning": "maschinelles Lernen"})
    lines = g.describe_terms([1, 0]).splitlines()
    assert sorted(lines) == ["'invoice' -> 'Rechnung'", "'machine learning' -> 'maschinelles Lernen'"]


def test_missing_allows_inflection_and_compounds():
    g = Glossary({"invoice": "Rechnung", "machine learning": "maschinelles Lernen", "tax": "Steuer"})
    i = {source: n for n, (source, _) in enumerate(g.terms)}
    assert g.missing("Die Grundlagen des maschinellen Lernens", [i["machine learning"]]) == []
    assert g.missing("Der Rechnungsprozess ist neu", [i["invoice"]]) == []
    assert g.missing("Alle Rechnungen sind da", [i["invoice"]]) == []
    assert g.missing("Die Steuern steigen", [i["tax"]]) == []
    assert g.missing("Die Faktura ist da", [i["invoice"]]) == [i["invoice"]]
    assert g.missing("Lernen ohne Maschine", [i["machine learning"]]) == [i["machine learning"]]


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
