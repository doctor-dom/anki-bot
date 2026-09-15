from pathlib import Path

from anki_bot.models import ContentKind, ItemInfo, QuestionReview
from anki_bot.outputs import (
    lecture_pack,
    lecture_pack_label,
    qbank_compiled_pack,
    qbank_run_pack,
    slugify_label,
    topic_from_group_id,
)


def test_slugify_label() -> None:
    assert slugify_label("Orthopedics") == "orthopedics"
    assert slugify_label("Primary Adrenal") == "primary-adrenal"


def test_topic_from_group_id() -> None:
    assert topic_from_group_id("01-adrenal-lecture") == "adrenal"
    assert topic_from_group_id("infectious-disease-lecture") == "infectious-disease"


def test_labeled_pack_paths(tmp_path: Path) -> None:
    pack = lecture_pack(tmp_path, "adrenal")
    assert pack.apkg_path == tmp_path / "ankideck" / "adrenal.apkg"
    assert pack.html_path == tmp_path / "adrenal-high-yield.html"
    assert pack.deck_name == "HUB::adrenal"

    qpack = qbank_run_pack(tmp_path, "abp", 12)
    assert qpack.apkg_path == tmp_path / "ankideck" / "qbank-abp12.apkg"
    assert qpack.html_path == tmp_path / "qbank-abp12-high-yield.html"

    compiled = qbank_compiled_pack(tmp_path, "abp")
    assert compiled.apkg_path == tmp_path / "ankideck" / "qbank-abp.apkg"


def test_lecture_pack_label_short_id() -> None:
    review = QuestionReview(
        id="infectious-disease-lecture",
        kind=ContentKind.LECTURE,
        item=ItemInfo(stem_gist="x"),
    )
    assert lecture_pack_label(review) == "infectious-disease"


def test_qbank_run_label() -> None:
    pack = qbank_run_pack(Path("output"), "endo", 2)
    assert pack.label == "qbank-endo2"
