from pathlib import Path

from anki_bot.discover import track_from_paths
from anki_bot.drive_sync import _drive_review_local_paths, _drive_review_remote_specs
from anki_bot.models import ContentKind, ItemInfo, QuestionReview
from anki_bot.outputs import iter_review_json_paths
from anki_bot.pipeline import load_all_reviews, save_review


def test_track_from_paths_endo_and_peds(tmp_path: Path) -> None:
    endo = tmp_path / "input" / "endo" / "q.pdf"
    peds = tmp_path / "input" / "peds" / "q.pdf"
    misc = tmp_path / "input" / "bare.pdf"
    assert track_from_paths(endo) == "endo"
    assert track_from_paths(peds) == "peds"
    assert track_from_paths(misc) == "misc"


def test_load_all_reviews_across_tracks_and_legacy(tmp_path: Path) -> None:
    output = tmp_path / "output"
    abp_review = QuestionReview(
        id="1-a",
        kind=ContentKind.QUESTION,
        track="abp",
        item=ItemInfo(stem_gist="a"),
    )
    endo_review = QuestionReview(
        id="2-b",
        kind=ContentKind.QUESTION,
        track="endo",
        item=ItemInfo(stem_gist="b"),
    )
    legacy_review = QuestionReview(
        id="3-c",
        kind=ContentKind.QUESTION,
        track="misc",
        item=ItemInfo(stem_gist="c"),
    )
    save_review(abp_review, output / "abp" / "reviews" / "1-a.json")
    save_review(endo_review, output / "endo" / "reviews" / "2-b.json")
    save_review(legacy_review, output / "reviews" / "3-c.json")

    paths = {p.name for p in iter_review_json_paths(output)}
    assert paths == {"1-a.json", "2-b.json", "3-c.json"}

    loaded = {r.id for r in load_all_reviews(output)}
    assert loaded == {"1-a", "2-b", "3-c"}


def test_drive_review_path_order() -> None:
    mounted = Path("/drive/output")
    local = _drive_review_local_paths(mounted, "12-endocrine", "abp")
    assert local[0] == mounted / "abp" / "reviews" / "12-endocrine.json"
    assert local[1] == mounted / "reviews" / "12-endocrine.json"

    remote = _drive_review_remote_specs("gdrive:anki-bot/output", "12-endocrine", "abp")
    assert remote[0] == "gdrive:anki-bot/output/abp/reviews/12-endocrine.json"
    assert remote[1] == "gdrive:anki-bot/output/reviews/12-endocrine.json"
