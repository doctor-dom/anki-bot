from pathlib import Path

from anki_bot.models import ContentKind, ItemInfo, QuestionReview, SourceFileFingerprint
from anki_bot.outputs import (
    PackKind,
    board_category_for_review,
    lecture_compiled_pack,
    lecture_pack,
    lecture_pack_label,
    match_board_category,
    packs_for_reviews,
    prune_stale_topic_files,
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

    topic_pack = next(p for p in packs if p.pack_kind == PackKind.QBANK_TOPIC)
    assert topic_pack.topic_key == "06-endocrinology-metabolic-genetics"
    assert topic_pack.html_path.name == "06-endocrinology-metabolic-genetics-high-yield.html"
    assert reviews_for_pack([review], topic_pack) == [review]


def test_board_categories_merge_fine_topics(tmp_path: Path) -> None:
    endocrine = QuestionReview(
        id="12-endocrine",
        kind=ContentKind.QUESTION,
        track="abp",
        item=ItemInfo(stem_gist="e"),
    )
    genetics = QuestionReview(
        id="4-genetics",
        kind=ContentKind.QUESTION,
        track="abp",
        item=ItemInfo(stem_gist="g"),
    )
    derm = QuestionReview(
        id="3-derm",
        kind=ContentKind.QUESTION,
        track="abp",
        item=ItemInfo(stem_gist="d"),
    )
    assert board_category_for_review(endocrine).key == board_category_for_review(genetics).key

    packs = packs_for_reviews(tmp_path, [endocrine, genetics, derm])
    topic_packs = [p for p in packs if p.pack_kind == PackKind.QBANK_TOPIC]
    assert [p.topic_key for p in topic_packs] == [
        "04-dermatology",
        "06-endocrinology-metabolic-genetics",
    ]
    endo_pack = topic_packs[1]
    assert [r.id for r in reviews_for_pack([endocrine, genetics, derm], endo_pack)] == [
        "12-endocrine",
        "4-genetics",
    ]


def test_board_category_aliases() -> None:
    expected = {
        "adolescent": "01-adolescent-behavioral",
        "sti": "01-adolescent-behavioral",
        "behavioral-health": "01-adolescent-behavioral",
        "substance-abuse": "01-adolescent-behavioral",
        "allergy": "02-allergy-heme-onc-rheum",
        "immunology": "02-allergy-heme-onc-rheum",
        "hematology": "02-allergy-heme-onc-rheum",
        "oncology": "02-allergy-heme-onc-rheum",
        "rheumatology": "02-allergy-heme-onc-rheum",
        "cardiology": "03-cardiology-pulmonology",
        "pulmonology": "03-cardiology-pulmonology",
        "dermatology": "04-dermatology",
        "emergency": "05-emergency-msk-ophtho-ent",
        "orthopedics": "05-emergency-msk-ophtho-ent",
        "musculoskeletal": "05-emergency-msk-ophtho-ent",
        "ophthalmology": "05-emergency-msk-ophtho-ent",
        "ent": "05-emergency-msk-ophtho-ent",
        "endocrinology": "06-endocrinology-metabolic-genetics",
        "t1dm-honeymoon": "06-endocrinology-metabolic-genetics",
        "metabolic-disorders": "06-endocrinology-metabolic-genetics",
        "genetics": "06-endocrinology-metabolic-genetics",
        "growth-hormone": "06-endocrinology-metabolic-genetics",
        "gastroenterology": "07-gastroenterology",
        "preventative-pediatrics": "08-preventative-pediatrics",
        "growth": "08-preventative-pediatrics",
        "development": "08-preventative-pediatrics",
        "vaccines": "08-preventative-pediatrics",
        "nutrition": "08-preventative-pediatrics",
        "infectious-disease": "09-infectious-disease",
        "neonatology": "10-neonatology",
        "nephrology": "11-nephrology",
        "neurology": "12-neurology",
        "unmapped-zebra": "other",
    }
    for slug, key in expected.items():
        assert match_board_category(slug).key == key, slug


def test_prune_stale_narrow_topic_files(tmp_path: Path) -> None:
    topics = tmp_path / "abp" / "topics"
    topics.mkdir(parents=True)
    old_html = topics / "endocrine-high-yield.html"
    old_html.write_text("old", encoding="utf-8")
    deck = tmp_path / "abp" / "ankideck"
    deck.mkdir()
    (deck / "endocrine.apkg").write_bytes(b"old")
    (deck / "all-abp.apkg").write_bytes(b"keep")
    (deck / "adrenal.apkg").write_bytes(b"lecture")

    question = QuestionReview(
        id="12-endocrine",
        kind=ContentKind.QUESTION,
        track="abp",
        item=ItemInfo(stem_gist="x"),
    )
    lecture = QuestionReview(
        id="01-adrenal-lecture",
        kind=ContentKind.LECTURE,
        track="abp",
        item=ItemInfo(stem_gist="x"),
    )
    packs = packs_for_reviews(tmp_path, [question, lecture])
    prune_stale_topic_files(tmp_path, packs)

    assert not old_html.exists()
    assert not (deck / "endocrine.apkg").exists()
    assert (deck / "all-abp.apkg").exists()
    assert (deck / "adrenal.apkg").exists()
