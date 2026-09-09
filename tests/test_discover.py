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
