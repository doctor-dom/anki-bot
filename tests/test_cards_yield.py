from anki_bot.cards import ensure_minimum_yield, filter_valid_cards, minimum_high_yield_text
from anki_bot.html_render import render_high_yield_page
from anki_bot.models import Category, ClozeCard, ContentKind, HighYieldItem, ItemInfo, QuestionReview
from anki_bot.outputs import board_category_for_review, match_board_category


def test_vsd_maps_to_cardiology() -> None:
    review = QuestionReview(
        id="12-vsd",
        kind=ContentKind.QUESTION,
        track="abp",
        item=ItemInfo(stem_gist="x"),
    )
    assert board_category_for_review(review).key == "03-cardiology-pulmonology"
    assert match_board_category("vsd").key == "03-cardiology-pulmonology"


def test_three_phrases_produce_three_cards() -> None:
    review = QuestionReview(
        id="1-test",
        kind=ContentKind.QUESTION,
        item=ItemInfo(stem_gist="infant murmur", correct_text="VSD"),
        high_yield=[
            HighYieldItem(text="holosystolic LLSB", category=Category.NEG, source="stem"),
            HighYieldItem(text="VSD", category=Category.TOPIC, source="explanation"),
            HighYieldItem(text="echo", category=Category.DX, source="explanation"),
        ],
        cards=[],
    )
    review = ensure_minimum_yield(review)
    assert len(review.cards) == 3
    assert all("{{c1::" in card.text for card in review.cards)


def test_empty_explanation_uses_question_line_and_cloze() -> None:
    review = QuestionReview(
        id="2-test",
        kind=ContentKind.QUESTION,
        item=ItemInfo(stem_gist="Teen with chest pain after exercise", correct_text="Pericarditis"),
        high_yield=[],
        cards=[],
    )
    review = ensure_minimum_yield(review)
    assert len(review.high_yield) == 1
    assert "Teen with chest pain" in review.high_yield[0].text
    assert len(review.cards) >= 1
    html = render_high_yield_page([review])
    assert "Teen with chest pain" in html


def test_existing_phrases_not_lengthened() -> None:
    review = QuestionReview(
        id="3-test",
        kind=ContentKind.QUESTION,
        item=ItemInfo(stem_gist="long stem ignored", correct_text="CAH"),
        high_yield=[HighYieldItem(text="elevated 17-OHP", category=Category.DX, source="explanation")],
        cards=[
            ClozeCard(
                text='<span class="hy-dx">{{c1::elevated 17-OHP}}</span>',
                source="explanation",
            )
        ],
    )
    before = review.high_yield[0].text
    review = filter_valid_cards(review)
    review = ensure_minimum_yield(review)
    assert review.high_yield[0].text == before
    assert len(review.high_yield) == 1
