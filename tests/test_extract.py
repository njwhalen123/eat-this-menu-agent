import os

from conftest import PRACTICE
from menu_agent import captures


def test_hidden_tab_panels_are_read_and_images_listed():
    cs = captures.load(os.path.join(PRACTICE, "P2"))
    c = cs.captures["P2-C1"]
    assert "Whole Branzino" in c.lines  # a dinner dish in a hidden panel
    assert c.ex.images and c.ex.images[0]["alt"].startswith("Chalkboard")
    assert not any("tab switcher" in ln for ln in c.lines)  # scripts dropped


def test_pdf_pages_and_links():
    cs = captures.load(os.path.join(PRACTICE, "P4"))
    c = cs.captures["P4-C1"]
    assert c.ex.pages == 2 and c.ex.line_pages[-1] == 2
    assert c.line_label(1).startswith("p1 ")
    cs3 = captures.load(os.path.join(PRACTICE, "P3"))
    urls = {ln["url"] for ln in cs3.captures["P3-C1"].ex.links}
    assert "https://larkspur-noodles.example/menu/brunch.html" in urls
    assert "https://larkspur-noodles.example/menu/brunch.html" not in cs3.by_url()


def test_hash_mismatch_is_refused(tmp_path):
    import json, shutil
    d = tmp_path / "P1"
    shutil.copytree(os.path.join(PRACTICE, "P1"), d)
    (d / "captures" / "menu.html").write_text("changed", encoding="utf-8")
    try:
        captures.load(str(d))
        assert False, "should refuse"
    except captures.CaptureError:
        pass
