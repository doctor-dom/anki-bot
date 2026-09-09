from pathlib import Path

from PIL import Image, ImageDraw

from anki_bot.model_select import FLASH_MODEL, PRO_MODEL, choose_model


def _make_png(path: Path, size: tuple[int, int], *, chart: bool = False) -> None:
    img = Image.new("RGB", size, "white")
    if chart:
        draw = ImageDraw.Draw(img)
        for x in range(0, size[0], 20):
            draw.line([(x, 0), (x, size[1])], fill="black", width=1)
        for y in range(0, size[1], 20):
            draw.line([(0, y), (size[0], y)], fill="black", width=1)
        draw.rectangle([40, 40, size[0] - 40, size[1] - 40], outline="red", width=3)
    img.save(path, format="PNG")


def test_auto_picks_flash_for_simple_image(tmp_path: Path) -> None:
    img = tmp_path / "simple.png"
    _make_png(img, (800, 600))
    choice = choose_model([img], requested="auto")
    assert choice.model == FLASH_MODEL
    assert choice.auto_selected


def test_auto_picks_pro_for_many_images(tmp_path: Path) -> None:
    paths = []
    for i in range(3):
        p = tmp_path / f"page_{i}.png"
        _make_png(p, (900, 700))
        paths.append(p)
    choice = choose_model(paths, requested="auto")
    assert choice.model == PRO_MODEL
    assert choice.auto_selected


def test_auto_picks_pro_for_chart_like_image(tmp_path: Path) -> None:
    img = tmp_path / "chart.png"
    _make_png(img, (1600, 1200), chart=True)
    choice = choose_model([img], requested="auto")
    assert choice.model == PRO_MODEL
    assert any("chart" in r or "dense" in r or "large" in r or "high-res" in r for r in choice.reasons)


def test_force_flash_override(tmp_path: Path) -> None:
    img = tmp_path / "chart.png"
    _make_png(img, (2000, 1500), chart=True)
    choice = choose_model([img], requested=FLASH_MODEL)
    assert choice.model == FLASH_MODEL
    assert not choice.auto_selected
