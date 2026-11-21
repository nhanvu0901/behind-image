"""B-019: an upload that is not a complete, decodable image is refused before it is stored."""
import pytest

from bti.media import api
from bti.media.imageinfo import readable_problem


def _png(path):
    from PIL import Image
    Image.new("RGB", (40, 30), (10, 20, 30)).save(path)
    return path


def test_good_png_is_readable(tmp_path):
    assert readable_problem(_png(tmp_path / "a.png")) is None


@pytest.mark.parametrize("data", [b"", b"not an image", b"\x89PNG\r\n\x1a\n" + b"\x00" * 500])
def test_junk_is_not_readable(tmp_path, data):
    f = tmp_path / "a.png"
    f.write_bytes(data)
    assert readable_problem(f)


def test_truncated_png_is_not_readable(tmp_path):
    f = _png(tmp_path / "a.png")
    f.write_bytes(f.read_bytes()[:-30])
    assert readable_problem(f)


def test_add_upload_refuses_junk_and_stores_nothing(tmp_path):
    proj = tmp_path / "p"
    (proj / "media").mkdir(parents=True)
    f = tmp_path / "x.png"
    f.write_bytes(b"junk")
    with pytest.raises(ValueError):
        api.add_upload(proj, f, {"licence": "CC0", "source_url": "http://x", "author": "me"})
    assert not list((proj / "media").iterdir())
