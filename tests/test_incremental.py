from pathlib import Path

import pytest

from anki_bot import pipeline as pipeline_mod
from anki_bot.pipeline import process_path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_lecture_review.json"
HTML_FIXTURE = Path(__file__).parent / "fixtures" / "sample_lecture.html"


def test_only_ids_forces_named_group_and_skips_the_rest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input" / "abp"
    input_dir.mkdir(parents=True)
    (input_dir / "01-adrenal-lecture.html").write_bytes(HTML_FIXTURE.read_bytes())
    (input_dir / "02-cardio-lecture.html").write_bytes(HTML_FIXTURE.read_bytes())
    output = tmp_path / "output"

    process_path(input_dir, output, review_only=True, fixture=FIXTURE)
    capsys.readouterr()

    calls: list[str] = []
    original = pipeline_mod._process_group

    def fake_process_group(group, output_root, **kwargs):  # noqa: ANN001
        calls.append(group.id)
        kwargs["fixture"] = FIXTURE
        return original(group, output_root, **kwargs)

    monkeypatch.setattr(pipeline_mod, "_process_group", fake_process_group)
    reviews = process_path(
        input_dir,
        output,
        review_only=True,
        only_ids={"01-adrenal-lecture"},
    )
    out = capsys.readouterr().out
    assert calls == ["01-adrenal-lecture"]
    assert len(reviews) == 1
    assert "Ran (1)" in out
    assert "Ignored (1" in out
    assert "02-cardio-lecture" in out
    assert "Reprocessing only: 01-adrenal-lecture" in out


def test_skip_unchanged_lecture(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_dir = tmp_path / "input" / "abp"
    input_dir.mkdir(parents=True)
    html = input_dir / "01-adrenal-lecture.html"
    html.write_bytes(HTML_FIXTURE.read_bytes())
    output = tmp_path / "output"

    process_path(input_dir, output, review_only=True, fixture=FIXTURE)
    process_path(input_dir, output, review_only=True)
    out = capsys.readouterr().out
    assert "Ignored" in out
    assert "01-adrenal-lecture" in out

    process_path(input_dir, output, review_only=True, fixture=FIXTURE, force=True)
    out_force = capsys.readouterr().out
    assert "Ran (1)" in out_force
