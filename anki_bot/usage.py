"""Gemini token usage and USD cost estimates."""

from __future__ import annotations

from dataclasses import dataclass

PRO_MODEL = "gemini-3.1-pro-preview"
PRO_INPUT_USD_PER_M = 2.0
PRO_OUTPUT_USD_PER_M = 12.0


@dataclass(frozen=True)
class UsageRecord:
    input_tokens: int
    output_tokens: int
    estimated_usd: float
    model: str = PRO_MODEL

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def estimate_usd(
    input_tokens: int,
    output_tokens: int,
    *,
    input_rate: float = PRO_INPUT_USD_PER_M,
    output_rate: float = PRO_OUTPUT_USD_PER_M,
) -> float:
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def usage_from_metadata(
    usage_metadata: object | None,
    *,
    model: str = PRO_MODEL,
) -> UsageRecord | None:
    if usage_metadata is None:
        return None

    input_tokens = int(
        getattr(usage_metadata, "prompt_token_count", 0)
        or getattr(usage_metadata, "input_token_count", 0)
        or 0
    )
    output_tokens = int(
        getattr(usage_metadata, "candidates_token_count", 0)
        or getattr(usage_metadata, "output_token_count", 0)
        or 0
    )
    if input_tokens == 0 and output_tokens == 0:
        return None

    return UsageRecord(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_usd=estimate_usd(input_tokens, output_tokens),
        model=model,
    )


def format_usd(amount: float) -> str:
    if amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.3f}"


def format_usage_line(
    label: str,
    usage: UsageRecord,
    *,
    lecture_hours: float | None = None,
) -> str:
    base = (
        f"[{label}] Gemini usage: {usage.input_tokens:,} in + "
        f"{usage.output_tokens:,} out (~{format_usd(usage.estimated_usd)})"
    )
    if lecture_hours and lecture_hours > 0:
        per_hour = usage.estimated_usd / lecture_hours
        return f"{base} · {lecture_hours:.1f} hr · {format_usd(per_hour)}/hr"
    return base


def project_50h(total_usd: float, total_lecture_hours: float) -> float:
    """Project cost for 50 hours at the observed $/hr rate."""
    if total_lecture_hours <= 0:
        return 0.0
    per_hour = total_usd / total_lecture_hours
    return per_hour * 50.0


def format_run_total(
    usages: list[UsageRecord],
    *,
    lecture_hours: float = 0.0,
) -> str:
    total_in = sum(u.input_tokens for u in usages)
    total_out = sum(u.output_tokens for u in usages)
    total_usd = sum(u.estimated_usd for u in usages)
    lines = [
        (
            f"Run total: {total_in:,} in + {total_out:,} out "
            f"(~{format_usd(total_usd)})"
            + (f" across {lecture_hours:.1f} lecture-hours" if lecture_hours > 0 else "")
        )
    ]
    if lecture_hours > 0:
        projected = project_50h(total_usd, lecture_hours)
        lines.append(
            f"At this rate, 50 hours of content ≈ {format_usd(projected)} "
            "(Google invoice is source of truth)"
        )
    return "\n".join(lines)
