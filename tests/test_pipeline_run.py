import time
from pathlib import Path

import pytest

import anki_bot.run_budget as run_budget_mod
from anki_bot import pipeline as pipeline_mod
from anki_bot.pipeline import _process_group, process_path
from anki_bot.run_budget import mark_run_started, run_budget_exceeded

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_run_budget_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANKI_BOT_RUN_BUDGET_MINUTES", "5")
    mark_run_started()
    monkeypatch.setattr(run_budget_mod, "_run_started_at", time.monotonic() - 400)
    assert run_budget_exceeded()


def test_process_continues_after_group_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("q-ok", "q-fail"):
        d = tmp_path / "input" / "abp" / name
        d.mkdir(parents=True)
        (d / "1.png").write_bytes(PNG)

    output = tmp_path / "output"
    calls = {"n": 0}

    def fake_process_group(group, output_root, **kwargs):
        calls["n"] += 1
        if group.id == "q-fail":
            raise RuntimeError("simulated Gemini timeout")
        kwargs["fixture"] = FIXTURE
        return _process_group(group, output_root, **kwargs)

    monkeypatch.setattr(pipeline_mod, "_process_group", fake_process_group)
    reviews = process_path(tmp_path / "input" / "abp", output, fixture=FIXTURE)
    assert calls["n"] == 2
    assert len(reviews) == 1
    assert (output / "abp" / "reviews" / "q-ok.json").is_file()
    assert not (output / "abp" / "reviews" / "q-fail.json").exists()
