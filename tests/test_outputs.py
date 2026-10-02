from pathlib import Path

from anki_bot.models import ContentKind, ItemInfo, QuestionReview, SourceFileFingerprint
from anki_bot.outputs import (
    PackKind,
    lecture_compiled_pack,
    lecture_pack,
    lecture_pack_label,
    packs_for_reviews,
    qbank_all_pack,
    qbank_folder_pack,
    qbank_topic_pack,
    review_input_folder_key,
    reviews_for_pack,
    slugify_label,
    topic_from_group_id,
    topic_key_for_review,
)


def test_slugify_label() -> None:
    assert slugify_label("Orthopedics") == "orthopedics"
    assert slugify_label("Primary Adrenal") == "primary-adrenal"


def test_topic_from_group_id() -> None:
    assert topic_from_group_id("01-adrenal-lecture") == "adrenal"
    assert topic_from_group_id("infectious-disease-lecture") == "infectious-disease"


def test_labeled_pack_paths(tmp_path: Path) -> None:
    pack = lecture_pack(tmp_path, "adrenal", track="abp")
    assert pack.apkg_path == tmp_path / "abp" / "ankideck" / "adrenal.apkg"
    assert pack.html_path == tmp_path / "abp" / "adrenal-high-yield.html"
    assert pack.deck_name == "HUB::adrenal"

    all_pack = qbank_all_pack(tmp_path, "abp")
    assert all_pack.apkg_path == tmp_path / "abp" / "ankideck" / "all-abp.apkg"
    assert all_pack.html_path == tmp_path / "abp" / "all-abp-high-yield.html"

    topic = qbank_topic_pack(tmp_path, "abp", "endocrine")
    assert topic.html_path == tmp_path / "abp" / "topics" / "endocrine-high-yield.html"
    assert topic.apkg_path == tmp_path / "abp" / "ankideck" / "endocrine.apkg"

    folder = qbank_folder_pack(tmp_path, "abp", "abp-qbank-10")
    assert folder.html_path == tmp_path / "abp" / "abp-qbank-10" / "abp-qbank-10-high-yield.html"
    assert folder.apkg_path == tmp_path / "abp" / "abp-qbank-10" / "ankideck" / "abp-qbank-10.apkg"


def test_lecture_pack_label_short_id() -> None:
    review = QuestionReview(
        id="infectious-disease-lecture",
        kind=ContentKind.LECTURE,
        item=ItemInfo(stem_gist="x"),
    )
    assert lecture_pack_label(review) == "infectious-disease"


def test_lecture_compiled_pack_path(tmp_path: Path) -> None:
    pack = lecture_compiled_pack(tmp_path, "abp")
    assert pack.pack_kind == PackKind.LECTURE_COMPILED
    assert pack.html_path == tmp_path / "abp" / "lectures-abp-high-yield.html"


def test_packs_include_lecture_compiled(tmp_path: Path) -> None:
    review = QuestionReview(
        id="01-adrenal-lecture",
        kind=ContentKind.LECTURE,
        track="abp",
        item=ItemInfo(stem_gist="x"),
    )
    packs = packs_for_reviews(tmp_path, [review])
    kinds = {p.pack_kind for p in packs}
    assert PackKind.LECTURE_COMPILED in kinds


def test_qbank_packs_all_topic_folder(tmp_path: Path) -> None:
    review = QuestionReview(
        id="12-endocrine",
        kind=ContentKind.QUESTION,
        track="abp",
        item=ItemInfo(stem_gist="x"),
        source_fingerprint=[
            SourceFileFingerprint(
                size=1,
                relpath="abp-qbank-10/12-endocrine.png",
                sha256="a",
            )
        ],
    )
    assert topic_key_for_review(review) == "endocrine"
    assert review_input_folder_key(review) == "abp-qbank-10"

    packs = packs_for_reviews(tmp_path, [review])
    kinds = {p.pack_kind for p in packs}
    assert kinds == {PackKind.QBANK_ALL, PackKind.QBANK_TOPIC, PackKind.QBANK_FOLDER}

    all_pack = next(p for p in packs if p.pack_kind == PackKind.QBANK_ALL)
    assert reviews_for_pack([review], all_pack) == [review]
