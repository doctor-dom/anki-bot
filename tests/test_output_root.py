from pathlib import Path

from anki_bot.paths import find_repo_root, resolve_output_root


def test_find_repo_root_from_nested_input(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    nested = tmp_path / "input" / "abp" / "case1"
    nested.mkdir(parents=True)
    assert find_repo_root(nested) == tmp_path.resolve()


def test_default_output_anchors_to_repo_when_cwd_nested(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    nested = tmp_path / "input" / "abp" / "case1"
    nested.mkdir(parents=True)
    html = nested / "lecture.html"
    html.write_text("<html><body>x</body></html>", encoding="utf-8")

    out = resolve_output_root("output", anchor_path=html, cwd=nested)
    assert out == (tmp_path / "output").resolve()


def test_custom_relative_output_uses_cwd(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    nested = tmp_path / "input" / "abp"
    nested.mkdir(parents=True)

    out = resolve_output_root("custom-out", anchor_path=nested, cwd=nested)
    assert out == (nested / "custom-out").resolve()
