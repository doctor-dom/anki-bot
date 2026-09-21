from anki_bot.usage import (
    FLASH_LITE_MODEL,
    FLASH_MODEL,
    PRO_MODEL,
    UsageRecord,
    estimate_usd,
    format_usage_line,
    project_50h,
    rates_for_model,
    usage_from_metadata,
)


def test_estimate_usd_calibration_pro() -> None:
    amount = estimate_usd(8200, 4100, model=PRO_MODEL)
    assert abs(amount - 0.0656) < 0.001


def test_estimate_usd_flash_cheaper() -> None:
    flash = estimate_usd(8200, 4100, model=FLASH_MODEL)
    pro = estimate_usd(8200, 4100, model=PRO_MODEL)
    assert flash < pro


def test_project_50h() -> None:
    projected = project_50h(0.066, 1.5)
    assert abs(projected - 2.2) < 0.05


def test_format_usage_line_with_hours() -> None:
    usage = UsageRecord(input_tokens=8200, output_tokens=4100, estimated_usd=0.066)
    line = format_usage_line("orthopedics", usage, lecture_hours=1.5)
    assert "8,200 in" in line
    assert "4,100 out" in line
    assert "/hr" in line


def test_flash_lite_rates_distinct_from_flash() -> None:
    lite_in, lite_out = rates_for_model(FLASH_LITE_MODEL)
    flash_in, flash_out = rates_for_model(FLASH_MODEL)
    assert lite_in < flash_in
    assert lite_out < flash_out


def test_usage_includes_thought_tokens() -> None:
    class Meta:
        prompt_token_count = 1000
        candidates_token_count = 500
        thoughts_token_count = 200

    record = usage_from_metadata(Meta(), model=FLASH_LITE_MODEL)
    assert record is not None
    assert record.output_tokens == 700
    assert record.thought_tokens == 200


def test_format_usage_line_input_note() -> None:
    usage = UsageRecord(input_tokens=100, output_tokens=50, estimated_usd=0.001, model=FLASH_LITE_MODEL)
    line = format_usage_line("q1", usage, input_note="OCR text")
    assert "OCR text" in line
