"""Estimate API cost before a full run."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from anki_bot.discover import ContentGroup
from anki_bot.drive_sync import discover_with_drive
from anki_bot.models import ContentKind, QuestionReview
from anki_bot.processed import should_skip_group
from anki_bot.usage import estimate_usd, format_usd, rates_for_model
from anki_bot.model_select import FLASH_MODEL, PRO_MODEL


@dataclass(frozen=True)
class CostAverages:
    question_usd: float
    lecture_usd: float
    question_model: str
    lecture_model: str
    sample_count: int


def _load_usage_averages(reviews_dir: Path, *, max_samples: int = 50) -> CostAverages | None:
    if not reviews_dir.is_dir():
        return None

    question_costs: list[tuple[float, str]] = []
    lecture_costs: list[tuple[float, str]] = []

    for path in sorted(reviews_dir.glob("*.json"), reverse=True):
        if len(question_costs) + len(lecture_costs) >= max_samples:
            break
        try:
            review = QuestionReview.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError):
            continue
        if review.usage is None or review.usage.estimated_usd <= 0:
            continue
        model = review.usage.model or PRO_MODEL
        if review.kind == ContentKind.LECTURE:
            lecture_costs.append((review.usage.estimated_usd, model))
        else:
            question_costs.append((review.usage.estimated_usd, model))

    if not question_costs and not lecture_costs:
        return None

    def avg(items: list[tuple[float, str]], default_model: str) -> tuple[float, str]:
        if not items:
            return 0.0, default_model
        return sum(c for c, _ in items) / len(items), items[0][1]

    q_avg, q_model = avg(question_costs, FLASH_MODEL)
    l_avg, l_model = avg(lecture_costs, FLASH_MODEL)
    return CostAverages(
        question_usd=q_avg,
        lecture_usd=l_avg,
        question_model=q_model,
        lecture_model=l_model,
        sample_count=len(question_costs) + len(lecture_costs),
    )


def _fallback_averages() -> CostAverages:
    """Conservative defaults when no review history exists."""
    q_in, q_out = 4000, 1500
    l_in, l_out = 12000, 3500
    return CostAverages(
        question_usd=estimate_usd(q_in, q_out, model=FLASH_MODEL),
        lecture_usd=estimate_usd(l_in, l_out, model=FLASH_MODEL),
        question_model=FLASH_MODEL,
        lecture_model=FLASH_MODEL,
        sample_count=0,
    )


@dataclass(frozen=True)
class EstimateReport:
    groups: list[ContentGroup]
    would_run: list[ContentGroup]
    would_skip: list[ContentGroup]
    estimated_usd: float
    averages: CostAverages


def estimate_path(
    input_path: Path,
    output_root: Path,
    *,
    force: bool = False,
) -> EstimateReport:
    groups, input_roots, _drive_warnings = discover_with_drive(input_path)
    if not groups:
        raise FileNotFoundError(f"No supported inputs found under {input_path}")

    reviews_dir = output_root / "reviews"
    averages = _load_usage_averages(reviews_dir) or _fallback_averages()

    would_run: list[ContentGroup] = []
    would_skip: list[ContentGroup] = []
    for group in groups:
        review_path = reviews_dir / f"{group.id}.json"
        if should_skip_group(
            group,
            review_path,
            force=force,
            input_roots=input_roots,
        ):
            would_skip.append(group)
        else:
            would_run.append(group)

    total = 0.0
    for group in would_run:
        if group.kind == ContentKind.LECTURE:
            total += averages.lecture_usd
        else:
            total += averages.question_usd

    return EstimateReport(
        groups=groups,
        would_run=would_run,
        would_skip=would_skip,
        estimated_usd=total,
        averages=averages,
    )


def format_estimate_report(report: EstimateReport) -> str:
    questions = sum(1 for g in report.would_run if g.kind == ContentKind.QUESTION)
    lectures = sum(1 for g in report.would_run if g.kind == ContentKind.LECTURE)
    lines = [
        f"Discovered {len(report.groups)} group(s): "
        f"{sum(1 for g in report.groups if g.kind == ContentKind.QUESTION)} question(s), "
        f"{sum(1 for g in report.groups if g.kind == ContentKind.LECTURE)} lecture(s)",
        f"Would call API: {len(report.would_run)} ({questions} question, {lectures} lecture)",
        f"Would skip (unchanged): {len(report.would_skip)}",
    ]
    avg = report.averages
    if avg.sample_count:
        lines.append(
            f"Using average cost from last {avg.sample_count} review(s): "
            f"~{format_usd(avg.question_usd)}/question ({avg.question_model}), "
            f"~{format_usd(avg.lecture_usd)}/lecture ({avg.lecture_model})"
        )
    else:
        lines.append(
            f"No usage history; using Flash defaults: "
            f"~{format_usd(avg.question_usd)}/question, ~{format_usd(avg.lecture_usd)}/lecture"
        )
    lines.append(f"Estimated API spend this run: ~{format_usd(report.estimated_usd)}")
    q_rate_in, _ = rates_for_model(avg.question_model)
    lines.append(f"(Rates reference: {avg.question_model} ≈ ${q_rate_in}/M input; invoice is source of truth)")
    return "\n".join(lines)
