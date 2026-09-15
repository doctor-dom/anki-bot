from pathlib import Path

from anki_bot.apkg import write_apkg
from anki_bot.gemini_review import review_images_from_fixture
from anki_bot.pipeline import build_from_reviews, process_path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def test_write_apkg(tmp_path: Path) -> None:
    review = review_images_from_fixture("sample", [], FIXTURE)
    apkg = tmp_path / "deck.apkg"
    count = write_apkg([review], apkg)
    assert count == 2
    assert apkg.exists()
    assert apkg.stat().st_size > 100


def test_process_with_fixture(tmp_path: Path) -> None:
    input_dir = tmp_path / "input" / "q1"
    input_dir.mkdir(parents=True)
    (input_dir / "1.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    output = tmp_path / "output"
    reviews = process_path(
        input_dir,
        output,
        review_only=False,
        fixture=FIXTURE,
    )
    assert len(reviews) == 1
    assert (output / "qbank-misc1-high-yield.html").exists()
    assert (output / "reviews" / "q1.json").exists()
    assert (output / "ankideck" / "qbank-misc1.apkg").exists()
    assert (output / "ankideck" / "qbank-misc.apkg").exists()


def test_two_questions_write_qbank_abp(tmp_path: Path) -> None:
    for name in ("q1", "q2"):
        input_dir = tmp_path / "input" / "abp" / name
        input_dir.mkdir(parents=True)
        (input_dir / "1.png").write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
        )
    output = tmp_path / "output"
    process_path(tmp_path / "input" / "abp", output, review_only=False, fixture=FIXTURE)
    assert (output / "ankideck" / "qbank-abp2.apkg").exists()
    assert (output / "ankideck" / "qbank-abp.apkg").exists()


def test_build_from_reviews(tmp_path: Path) -> None:
    input_dir = tmp_path / "input" / "q1"
    input_dir.mkdir(parents=True)
    (input_dir / "1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    output = tmp_path / "output"
    process_path(input_dir, output, review_only=True, fixture=FIXTURE)
    reviews, count = build_from_reviews(output / "reviews", output)
    assert len(reviews) == 1
    assert count == 2
