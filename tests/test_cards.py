import pytest

from anki_bot.cards import CardValidationError, filter_valid_cards, validate_cloze_text
from anki_bot.models import ClozeCard, ItemInfo, QuestionReview, SourceType


def test_valid_cloze() -> None:
    validate_cloze_text("{{c1::CAH}} is common.")


def test_missing_cloze_raises() -> None:
    with pytest.raises(CardValidationError):
        validate_cloze_text("No cloze here")


def test_filter_rejects_invalid() -> None:
    review = QuestionReview(
        id="test",
        item=ItemInfo(stem_gist="x"),
        cards=[
            ClozeCard(text="{{c1::ok}}", source=SourceType.EXPLANATION),
            ClozeCard(text="bad", source=SourceType.EXPLANATION),
        ],
    )
    filtered = filter_valid_cards(review)
    assert len(filtered.cards) == 1
    assert any("rejected" in w.lower() for w in filtered.warnings)
