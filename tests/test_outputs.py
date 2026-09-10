from pathlib import Path

from anki_bot.models import ContentKind, ItemInfo, QuestionReview
from anki_bot.outputs import lecture_pack, qbank_pack, slugify_label, topic_from_group_id


def test_slugify_label() -> None:
    assert slugify_label("Orthopedics") == "orthopedics"
    assert slugify_label("Primary Adrenal") == "primary-adrenal"


def test_topic_from_group_id() -> None:
    assert topic_from_group_id("01-adrenal-lecture") == "adrenal"


def test_labeled_pack_paths(tmp_path: Path) -> None:
    pack = lecture_pack(tmp_path, "adrenal")
    assert pack.apkg_path == tmp_path / "adrenal.apkg"
    assert pack.html_path == tmp_path / "adrenal-high-yield.html"
    assert pack.deck_name == "HUB::adrenal"

    qpack = qbank_pack(tmp_path, 12)
    assert qpack.apkg_path == tmp_path / "qbank12.apkg"
    assert qpack.html_path == tmp_path / "qbank12-high-yield.html"


def test_qbank_count_from_reviews() -> None:
    reviews = [
        QuestionReview(id="q1", kind=ContentKind.QUESTION, item=ItemInfo(stem_gist="a")),
        QuestionReview(id="q2", kind=ContentKind.QUESTION, item=ItemInfo(stem_gist="b")),
    ]
    pack = qbank_pack(Path("output"), len(reviews))
    assert pack.label == "qbank2"
