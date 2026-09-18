from anki_bot.card_budget import (
    LONG_LECTURE_HARD,
    LONG_LECTURE_SOFT,
    QUESTION_HARD,
    SHORT_LECTURE_HARD,
    SHORT_LECTURE_SOFT,
    budget_for_group,
    budget_for_lecture,
    budget_for_question,
)
from anki_bot.models import ContentKind


def test_question_budget() -> None:
    budget = budget_for_question()
    assert budget.soft_min == 1
    assert budget.soft_max == 5
    assert budget.hard_max == QUESTION_HARD


def test_bulk_qbank_budget(monkeypatch) -> None:
    monkeypatch.setenv("ANKI_BOT_BULK_QBANK", "1")
    budget = budget_for_question()
    assert budget.soft_max == 3
    assert budget.hard_max == 3


def test_short_lecture_budget() -> None:
    budget, warnings = budget_for_lecture(lecture_hours=0.5, char_count=5000)
    assert budget.soft_min == SHORT_LECTURE_SOFT[0]
    assert budget.soft_max == SHORT_LECTURE_SOFT[1]
    assert budget.hard_max == SHORT_LECTURE_HARD
    assert not warnings


def test_long_lecture_budget() -> None:
    budget, _ = budget_for_lecture(lecture_hours=1.5, char_count=20000)
    assert budget.soft_min == LONG_LECTURE_SOFT[0]
    assert budget.soft_max == LONG_LECTURE_SOFT[1]
    assert budget.hard_max == LONG_LECTURE_HARD


def test_lecture_hours_fallback_from_chars() -> None:
    budget, warnings = budget_for_lecture(lecture_hours=None, char_count=18000)
    assert budget.lecture_hours == 1.0
    assert budget.hard_max == LONG_LECTURE_HARD
    assert any("estimated" in w.lower() for w in warnings)


def test_max_cards_override() -> None:
    budget = budget_for_question(max_cards_override=3)
    assert budget.hard_max == 3
    assert budget.soft_max == 3


def test_budget_for_group_question() -> None:
    budget, warnings = budget_for_group(ContentKind.QUESTION)
    assert budget.hard_max == QUESTION_HARD
    assert warnings == []
