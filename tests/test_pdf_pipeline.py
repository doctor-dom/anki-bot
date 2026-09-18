from pathlib import Path

from anki_bot.pipeline import process_path

QUESTION_FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def test_process_two_abp_pdfs_builds_qbank_packs(tmp_path: Path) -> None:
    batch = tmp_path / "input" / "abp" / "abp-qbank-2"
    batch.mkdir(parents=True)
    (batch / "1 - first item.pdf").write_bytes(b"%PDF-1.4")
    (batch / "2 - second item.pdf").write_bytes(b"%PDF-1.4")
    output = tmp_path / "output"

    reviews = process_path(
        tmp_path / "input",
        output,
        review_only=False,
        fixture=QUESTION_FIXTURE,
    )
    assert len(reviews) == 2
    assert (output / "ankideck" / "qbank-abp2.apkg").exists()
    assert (output / "ankideck" / "qbank-abp.apkg").exists()
    for review in reviews:
        assert review.source_pdfs
        assert review.track == "abp"
