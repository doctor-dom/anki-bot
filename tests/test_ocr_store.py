from pathlib import Path

from anki_bot.image_ocr import PngPrepareResult
from anki_bot.ocr_store import read_png_ocr_text, write_png_ocr_artifact


def test_write_and_read_png_ocr_artifact(tmp_path: Path) -> None:
    result = PngPrepareResult(
        text="=== stem.png ===\nChild with murmur",
        used_vision=False,
        vision_paths=(),
        used_ocr=True,
        warnings=("example",),
    )
    rel = write_png_ocr_artifact(
        tmp_path,
        "abp",
        "12-vsd",
        result,
        source_images=["/input/12-vsd.png"],
    )
    assert rel == "ocr/12-vsd.json"
    assert (tmp_path / "abp" / "ocr" / "12-vsd.txt").read_text(encoding="utf-8") == result.text
    assert read_png_ocr_text(tmp_path, "abp", "12-vsd") == result.text
    meta = (tmp_path / "abp" / "ocr" / "12-vsd.json").read_text(encoding="utf-8")
    assert "12-vsd" in meta
    assert "used_ocr" in meta
