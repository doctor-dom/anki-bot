from pathlib import Path

from anki_bot.html_extract import (
    collect_lecture_image_paths,
    combine_lecture_html,
    extract_html_image_paths,
    extract_html_text,
    parse_duration,
    parse_lecture_meta_from_html,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_lecture.html"


def test_extract_html_text() -> None:
    text = extract_html_text(FIXTURE)
    assert "Primary adrenal insufficiency" in text
    assert "ACTH stimulation test" in text
    assert "<p>" not in text


def test_combine_lecture_html() -> None:
    text, warnings, meta = combine_lecture_html([FIXTURE], group_id="01-adrenal-lecture")
    assert "mineralocorticoid replacement" in text
    assert meta.topic == "adrenal"
    assert meta.hours is None
    assert not warnings


def test_parse_duration_variants() -> None:
    assert parse_duration("1.5") == 1.5
    assert parse_duration("1.5h") == 1.5
    assert parse_duration("90min") == 1.5
    assert parse_duration("1:30") == 1.5


def test_extract_html_image_paths(tmp_path: Path) -> None:
    slide = tmp_path / "slide.png"
    slide.write_bytes(b"\x89PNG\r\n\x1a\n")
    html = tmp_path / "lecture.html"
    html.write_text('<html><body><p>Notes</p><img src="slide.png"></body></html>', encoding="utf-8")
    paths = extract_html_image_paths(html)
    assert paths == [slide.resolve()]
    assert collect_lecture_image_paths([html]) == [str(slide.resolve())]


def test_parse_lecture_meta_from_html() -> None:
    html = """
    <html><head>
      <meta name="lecture-hours" content="1.5">
      <meta name="lecture-topic" content="Orthopedics">
    </head><body><p>Notes</p></body></html>
    """
    meta = parse_lecture_meta_from_html(html)
    assert meta.hours == 1.5
    assert meta.topic == "orthopedics"
