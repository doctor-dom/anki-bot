from pathlib import Path

from anki_bot.discover import discover_questions


def test_folder_is_one_question(tmp_path: Path) -> None:
    folder = tmp_path / "q1"
    folder.mkdir()
    (folder / "1.png").write_bytes(b"fake")
    (folder / "2.png").write_bytes(b"fake")
    groups = discover_questions(tmp_path)
    assert len(groups) == 1
    assert groups[0].id == "q1"
    assert len(groups[0].image_paths) == 2


def test_numbered_topic_grouping(tmp_path: Path) -> None:
    (tmp_path / "12-endocrine-part1.png").write_bytes(b"fake")
    (tmp_path / "12-endocrine-part2.png").write_bytes(b"fake")
    (tmp_path / "12-endocrine-explanation.png").write_bytes(b"fake")
    (tmp_path / "13-cardio-image1.png").write_bytes(b"fake")
    groups = discover_questions(tmp_path)
    assert len(groups) == 2
    by_id = {g.id: g for g in groups}
    assert by_id["12-endocrine"].image_paths == tuple(
        sorted(
            [
                tmp_path / "12-endocrine-explanation.png",
                tmp_path / "12-endocrine-part1.png",
                tmp_path / "12-endocrine-part2.png",
            ],
            key=lambda p: p.name.lower(),
        )
    )
    assert len(by_id["13-cardio"].image_paths) == 1


def test_numbered_topic_with_hyphenated_part(tmp_path: Path) -> None:
    (tmp_path / "12-endocrine-part-1-stem.png").write_bytes(b"fake")
    (tmp_path / "12-endocrine-image-2.png").write_bytes(b"fake")
    groups = discover_questions(tmp_path)
    assert len(groups) == 1
    assert groups[0].id == "12-endocrine"
    assert len(groups[0].image_paths) == 2


def test_two_part_filename_is_single_question(tmp_path: Path) -> None:
    (tmp_path / "12-endocrine.png").write_bytes(b"fake")
    groups = discover_questions(tmp_path)
    assert len(groups) == 1
    assert groups[0].id == "12-endocrine"


def test_legacy_prefix_grouping(tmp_path: Path) -> None:
    (tmp_path / "item_1.png").write_bytes(b"fake")
    (tmp_path / "item_2.png").write_bytes(b"fake")
    (tmp_path / "solo.png").write_bytes(b"fake")
    groups = discover_questions(tmp_path)
    assert len(groups) == 2
    ids = {g.id for g in groups}
    assert "item" in ids
    assert "solo" in ids


def test_qbank_pdf_filename_parsing(tmp_path: Path) -> None:
    input_abp = tmp_path / "input" / "abp" / "abp-qbank-10"
    input_abp.mkdir(parents=True)
    pdf = input_abp / "10 - T1DM honeymoon.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    groups = discover_questions(tmp_path / "input")
    assert len(groups) == 1
    assert groups[0].id == "10-t1dm-honeymoon"
    assert groups[0].track == "abp"
    assert groups[0].pdf_paths == (pdf,)


def test_qbank_pdf_batch_folder_is_ten_groups(tmp_path: Path) -> None:
    batch = tmp_path / "input" / "abp" / "abp-qbank-10"
    batch.mkdir(parents=True)
    for n in range(1, 11):
        (batch / f"{n} - topic {n}.pdf").write_bytes(b"pdf")
    groups = discover_questions(tmp_path / "input")
    assert len(groups) == 10
    assert "abp-qbank-10" not in {g.id for g in groups}


def test_recursive_input_finds_nested_pdfs(tmp_path: Path) -> None:
    nested = tmp_path / "input" / "abp" / "batch" / "nested"
    nested.mkdir(parents=True)
    (nested / "3 - nested item.pdf").write_bytes(b"pdf")
    groups = discover_questions(tmp_path / "input")
    assert len(groups) == 1
    assert groups[0].id == "3-nested-item"


def test_qbank_pdf_hyphenated_topic(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    (folder / "10 - type-1-dm.pdf").write_bytes(b"pdf")
    groups = discover_questions(folder)
    assert len(groups) == 1
    assert groups[0].id == "10-type-1-dm"
