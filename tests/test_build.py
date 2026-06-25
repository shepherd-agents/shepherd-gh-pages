import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build import (  # noqa: E402
    parse_front_matter,
    extract_sidenotes,
    convert_callouts,
    convert_figures,
    _plain,
    render_post,
    format_date,
)


# ---- front-matter ----
def test_parse_front_matter_basic():
    meta, body = parse_front_matter('---\ntitle: "Hi"\ndate: "2026-06-15"\n---\nHello\n')
    assert meta["title"] == "Hi"
    assert meta["date"] == "2026-06-15"
    assert body == "Hello\n"


def test_parse_front_matter_none():
    meta, body = parse_front_matter("No front matter\n")
    assert meta == {}
    assert body == "No front matter\n"


# ---- sidenotes ----
def test_extract_sidenotes_simple():
    body, notes = extract_sidenotes("Claim.^[a note] More.")
    assert body == "Claim.@@SN0@@ More."
    assert notes == ["a note"]


def test_extract_sidenotes_with_link():
    body, notes = extract_sidenotes("X.^[see [foo](http://b) here] Y.")
    assert body == "X.@@SN0@@ Y."
    assert notes == ["see [foo](http://b) here"]


def test_extract_sidenotes_multiple():
    body, notes = extract_sidenotes("a^[one]b^[two]c")
    assert body == "a@@SN0@@b@@SN1@@c"
    assert notes == ["one", "two"]


def test_extract_sidenotes_none():
    body, notes = extract_sidenotes("plain ^ not a note [x]")
    assert notes == []
    assert body == "plain ^ not a note [x]"


# ---- callouts ----
def test_convert_callouts_tldr():
    md = "> [!tldr]\n> hello **world**\n\nafter"
    out = convert_callouts(md, render_inner=lambda s: "<p>R:" + s + "</p>")
    assert 'class="callout callout--tldr"' in out
    assert "R:hello **world**" in out
    assert "after" in out


def test_convert_callouts_passthrough():
    md = "> a normal quote\n> second line"
    out = convert_callouts(md, render_inner=lambda s: "X")
    assert "callout" not in out
    assert "a normal quote" in out


# ---- figures ----
def test_convert_figures():
    md = "![**Fig 1.** A chart](../assets/fig-cro.png)"
    out = convert_figures(md, render_caption=lambda s: "<em>" + s + "</em>")
    assert "<figure>" in out
    assert 'src="../assets/fig-cro.png"' in out
    assert "Fig 1." in out
    assert 'alt="Fig 1. A chart"' in out


def test_plain_strips_markdown():
    assert _plain("**Bold** and [link](u)") == "Bold and link"


# ---- pipeline ----
def test_render_post_sidenote_and_callout():
    text = (
        '---\ntitle: "T"\n---\n'
        "## Sec\n\nClaim.^[note with [a](b)] end\n\n"
        "> [!insight]\n> deep thought\n"
    )
    meta, html, _ = render_post(text)
    assert meta["title"] == "T"
    assert 'class="sn"' in html
    assert 'href="b"' in html
    assert "callout--insight" in html
    assert "<h2" in html


def test_render_post_figure():
    text = "---\ntitle: T\n---\n![**F1.** cap](../assets/fig-cro.png)\n"
    _, html, _ = render_post(text)
    assert "<figure>" in html
    assert "fig-cro.png" in html
    assert "<strong>F1.</strong>" in html


def test_render_post_toc_built():
    text = "---\ntitle: T\n---\n## Alpha\n\n## Beta\n"
    _, _, toc = render_post(text)
    assert 'class="toc"' in toc
    assert "Alpha" in toc and "Beta" in toc


def test_format_date():
    assert format_date("2026-06-15") == "June 15, 2026"
    assert format_date("not a date") == "not a date"


def test_shepherd_brand_token():
    _, html, _ = render_post("---\ntitle: T\n---\nWe build :shepherd: on it.\n")
    assert ":shepherd:" not in html
    assert 'class="brand"' in html
    assert ">Shepherd</span>" in html
