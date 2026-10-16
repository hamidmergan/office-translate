from office_translate import __version__
from office_translate.cli import main


def args(server, *extra):
    return [*extra, "--base-url", server.base_url, "--model", "m"]


def test_single_file(tmp_path, server, capsys):
    src = tmp_path / "a.md"
    src.write_text("hello", encoding="utf-8")
    assert main(args(server, str(src), "--to", "German")) == 0
    assert (tmp_path / "a.german.md").read_text(encoding="utf-8") == "HELLO"
    assert "Wrote" in capsys.readouterr().err


def test_existing_output_gets_new_name(tmp_path, server):
    src = tmp_path / "a.txt"
    src.write_text("hello", encoding="utf-8")
    (tmp_path / "a.de.txt").write_text("old", encoding="utf-8")
    assert main(args(server, str(src), "--to", "de")) == 0
    assert (tmp_path / "a.de.txt").read_text(encoding="utf-8") == "old"
    assert (tmp_path / "a.de-1.txt").read_text(encoding="utf-8") == "HELLO"


def test_output_file(tmp_path, server):
    src = tmp_path / "a.txt"
    src.write_text("hello", encoding="utf-8")
    out = tmp_path / "result.txt"
    assert main(args(server, str(src), "--to", "de", "-o", str(out))) == 0
    assert out.read_text(encoding="utf-8") == "HELLO"


def test_many_files_to_folder(tmp_path, server):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.md"
    a.write_text("one", encoding="utf-8")
    b.write_text("two", encoding="utf-8")
    out = tmp_path / "out"
    assert main(args(server, str(a), str(b), "--to", "de", "-o", str(out))) == 0
    assert (out / "a.de.txt").read_text(encoding="utf-8") == "ONE"
    assert (out / "b.de.md").read_text(encoding="utf-8") == "TWO"


def test_many_files_output_is_file(tmp_path, server, capsys):
    a = tmp_path / "a.txt"
    a.write_text("one", encoding="utf-8")
    target = tmp_path / "x.txt"
    target.write_text("", encoding="utf-8")
    assert main(args(server, str(a), str(a), "--to", "de", "-o", str(target))) == 2
    assert "folder" in capsys.readouterr().err


def test_one_bad_file_continues(tmp_path, server, capsys):
    good = tmp_path / "good.txt"
    good.write_text("fine", encoding="utf-8")
    assert main(args(server, str(tmp_path / "missing.txt"), str(good), "--to", "de")) == 1
    assert (tmp_path / "good.de.txt").exists()
    assert "missing.txt" in capsys.readouterr().err


def test_glossary_flag(tmp_path, server):
    src = tmp_path / "a.txt"
    src.write_text("the invoice", encoding="utf-8")
    gl = tmp_path / "terms.csv"
    gl.write_text("invoice,Rechnung\n", encoding="utf-8")
    assert main(args(server, str(src), "--to", "de", "--glossary", str(gl))) == 0
    assert (tmp_path / "a.de.txt").read_text(encoding="utf-8") == "THE Rechnung"


def test_missing_config(tmp_path, capsys):
    src = tmp_path / "a.txt"
    src.write_text("hello", encoding="utf-8")
    assert main([str(src), "--to", "de"]) == 2
    assert "OFFICE_TRANSLATE_BASE_URL" in capsys.readouterr().err


def test_env_config(tmp_path, server, monkeypatch):
    monkeypatch.setenv("OFFICE_TRANSLATE_BASE_URL", server.base_url)
    monkeypatch.setenv("OFFICE_TRANSLATE_MODEL", "m")
    src = tmp_path / "a.txt"
    src.write_text("hello", encoding="utf-8")
    assert main([str(src), "--to", "de"]) == 0


def test_bad_glossary(tmp_path, server, capsys):
    src = tmp_path / "a.txt"
    src.write_text("hello", encoding="utf-8")
    assert main(args(server, str(src), "--to", "de", "--glossary", str(tmp_path / "no.csv"))) == 2
    assert "Glossary file not found" in capsys.readouterr().err


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert __version__ in capsys.readouterr().out
