import warnings
from pathlib import Path

from anki_bot.apkg import build_deck, escape_field_for_genanki, write_apkg
from anki_bot.models import ClozeCard, ContentKind, ItemInfo, QuestionReview, SourceType
from anki_bot.gemini_review import review_images_from_fixture
from anki_bot.pipeline import build_from_reviews, process_path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def test_escape_field_preserves_img_tags() -> None:
    raw = 'Pearl <img src="12-endocrine-0.png">'
    escaped = escape_field_for_genanki(raw)
    assert '<img src="12-endocrine-0.png">' in escaped


def test_escape_field_preserves_spans() -> None:
    raw = (
        'Infants < 24 months need {{c1::<span class="hy-dx">UA culture</span>}} and risk < 1%.'
    )
    escaped = escape_field_for_genanki(raw)
    assert "< 24" not in escaped
    assert "&lt; 24" in escaped
    assert '<span class="hy-dx">' in escaped
    assert "</span>" in escaped
    assert "&lt; 1%" in escaped


def test_write_apkg_no_genanki_html_warnings(tmp_path: Path) -> None:
    review = QuestionReview(
        id="lt-test",
        item=ItemInfo(stem_gist="x"),
        cards=[
            ClozeCard(
                text='Age < 7; Tdap with {{c1::<span class="hy-tx">vaccine</span>}}.',
                extra="Incidence < 1%.",
                source=SourceType.EXPLANATION,
            )
        ],
    )
    apkg = tmp_path / "deck.apkg"
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        count = write_apkg([review], apkg)
    assert count == 1
    assert apkg.exists()


def test_write_apkg_stem_extra_images(tmp_path: Path) -> None:
    img = tmp_path / "1.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    review = QuestionReview(
        id="q-stem-img",
        kind=ContentKind.QUESTION,
        item=ItemInfo(stem_gist="x"),
        source_images=[str(img)],
        cards=[
            ClozeCard(text="{{c1::A}}", extra="", source=SourceType.EXPLANATION),
            ClozeCard(text="{{c1::B}}", extra="note", source=SourceType.STEM),
        ],
    )
    deck, media = build_deck([review])
    assert media == [str(img.resolve())]
    assert len(deck.notes) == 2
    assert '<img src="q-stem-img-0.png">' in deck.notes[1].fields[1]
    assert "img" not in deck.notes[0].fields[1]

    apkg = tmp_path / "deck.apkg"
    count = write_apkg([review], apkg)
    assert count == 2
    assert apkg.stat().st_size > 200


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
    assert (output / "q1" / "all-q1-high-yield.html").exists()
    assert (output / "q1" / "reviews" / "q1.json").exists()
    assert not (output / "q1" / "reviews" / "q1.html").exists()
    assert (output / "q1" / "ankideck" / "all-q1.apkg").exists()


def test_two_questions_write_qbank_abp(tmp_path: Path) -> None:
    for name in ("q1", "q2"):
        input_dir = tmp_path / "input" / "abp" / name
        input_dir.mkdir(parents=True)
        (input_dir / "1.png").write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
        )
    output = tmp_path / "output"
    process_path(tmp_path / "input" / "abp", output, review_only=False, fixture=FIXTURE)
    assert (output / "abp" / "ankideck" / "all-abp.apkg").exists()
    assert (output / "abp" / "q1" / "ankideck" / "q1.apkg").exists()
    assert (output / "abp" / "q2" / "ankideck" / "q2.apkg").exists()


def test_build_from_reviews(tmp_path: Path) -> None:
    input_dir = tmp_path / "input" / "q1"
    input_dir.mkdir(parents=True)
    (input_dir / "1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    output = tmp_path / "output"
    process_path(input_dir, output, review_only=True, fixture=FIXTURE)
    reviews, count = build_from_reviews(output / "q1" / "reviews", output)
    assert len(reviews) == 1
    assert count >= 2
