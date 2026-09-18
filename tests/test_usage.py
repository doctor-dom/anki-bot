from anki_bot.usage import estimate_usd, format_usage_line, project_50h, FLASH_MODEL, PRO_MODEL
from anki_bot.usage import UsageRecord


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
