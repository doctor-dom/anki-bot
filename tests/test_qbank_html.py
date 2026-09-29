from pathlib import Path

from anki_bot.discover import ContentKind, discover_content, html_content_kind
from anki_bot.html_extract import combine_question_html, extract_question_html_text
from anki_bot.pipeline import process_path

QUESTION_FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"
QBANK_HTML = Path(__file__).parent / "fixtures" / "sample_qbank_question.html"
LECTURE_HTML = Path(__file__).parent / "fixtures" / "sample_lecture.html"


def test_html_content_kind_qbank_folder(tmp_path: Path) -> None:
    path = tmp_path / "input" / "abp" / "qbank-html" / "12-endocrine.html"
    path.parent.mkdir(parents=True)
    path.write_bytes(QBANK_HTML.read_bytes())
    assert html_content_kind(path) == ContentKind.QUESTION
    groups = discover_content(tmp_path / "input")
    assert len(groups) == 1
    assert groups[0].kind == ContentKind.QUESTION
    assert groups[0].id == "12-endocrine"
    assert groups[0].track == "abp"
    assert groups[0].html_paths == (path,)


def test_html_content_kind_meta_question(tmp_path: Path) -> None:
    path = tmp_path / "input" / "abp" / "12-endocrine.html"
    path.parent.mkdir(parents=True)
    path.write_text(
        "<html><head><meta name=\"anki-bot-kind\" content=\"question\"></head>"
        "<body><p>Stem</p></body></html>",
        encoding="utf-8",
    )
    assert html_content_kind(path) == ContentKind.QUESTION


def test_lecture_html_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "input" / "abp" / "01-adrenal-lecture.html"
    path.parent.mkdir(parents=True)
    path.write_bytes(LECTURE_HTML.read_bytes())
    groups = discover_content(tmp_path / "input")
    assert len(groups) == 1
    assert groups[0].kind == ContentKind.LECTURE
    assert groups[0].id == "01-adrenal-lecture"


def test_extract_question_html_preserves_hy_spans(tmp_path: Path) -> None:
    path = tmp_path / "q.html"
    path.write_bytes(QBANK_HTML.read_bytes())
    text = extract_question_html_text(path)
    assert '<span class="hy-topic">' in text
    assert "21-hydroxylase deficiency" in text
    assert "plain lecture strip" not in text


def test_process_qbank_html_fixture(tmp_path: Path) -> None:
    folder = tmp_path / "input" / "abp" / "qbank-html"
    folder.mkdir(parents=True)
    html = folder / "12-endocrine.html"
    html.write_bytes(QBANK_HTML.read_bytes())
    output = tmp_path / "output"
    reviews = process_path(
        tmp_path / "input",
        output,
        review_only=False,
        fixture=QUESTION_FIXTURE,
    )
    assert len(reviews) == 1
    assert reviews[0].kind == ContentKind.QUESTION
    assert (output / "abp" / "reviews" / "12-endocrine.json").exists()
    assert (output / "abp" / "ankideck" / "qbank-abp.apkg").exists()
    assert (output / "abp" / "ankideck" / "qbank-abp1.apkg").exists()


def test_combine_question_html(tmp_path: Path) -> None:
    path = tmp_path / "a.html"
    path.write_bytes(QBANK_HTML.read_bytes())
    combined, warnings = combine_question_html([path])
    assert not warnings
    assert "=== a.html ===" in combined
