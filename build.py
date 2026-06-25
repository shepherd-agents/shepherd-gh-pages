"""Generate blog/site/blog/index.html from blog/content/shepherd.md.

Run:
    uv run --with markdown --with pyyaml --with jinja2 --with pygments \
        python blog/build.py

The content file is YAML front-matter + markdown + a small custom dialect
(documented in blog/content/DIALECT.md):
  - ^[ ... ]      inline sidenote, rendered as a Tufte margin note
  - > [!tldr]     TL;DR callout box     > [!insight]   insight callout box
  - ![cap](src)   a standalone image line becomes a <figure> with caption
  - [TOC]         expanded in place to the table of contents
"""
import os
import re
from datetime import datetime

import yaml
import markdown as _md
from jinja2 import Environment, FileSystemLoader

_HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------
# front-matter
# --------------------------------------------------------------------------
def parse_front_matter(text):
    """Split a leading YAML front-matter block (--- ... ---) from the body.
    Returns (meta: dict, body: str); ({}, text) when there is no front-matter."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    meta = yaml.safe_load(text[4:end]) or {}
    return meta, text[end + 5:]


# --------------------------------------------------------------------------
# sidenotes:  ^[ ... ]  ->  token @@SN{i}@@
# --------------------------------------------------------------------------
def extract_sidenotes(body):
    """Replace each inline sidenote ^[ ... ] with a token @@SN{i}@@ and collect
    the note markdown. Bracket-balanced, so notes may contain [links](url).
    Returns (body_with_tokens, notes)."""
    notes, out, i, n = [], [], 0, len(body)
    while i < n:
        if body[i] == "^" and i + 1 < n and body[i + 1] == "[":
            depth, j = 1, i + 2
            while j < n and depth > 0:
                if body[j] == "[":
                    depth += 1
                elif body[j] == "]":
                    depth -= 1
                j += 1
            if depth == 0:
                out.append("@@SN%d@@" % len(notes))
                notes.append(body[i + 2:j - 1])
                i = j
                continue
        out.append(body[i])
        i += 1
    return "".join(out), notes


# --------------------------------------------------------------------------
# callouts and figures
# --------------------------------------------------------------------------
_CALLOUT_RE = re.compile(r"^>\s*\[!(\w+)\]\s*$")
_FIG_RE = re.compile(r"^!\[(?P<cap>.*)\]\((?P<src>[^)]+)\)\s*$")


def _plain(text):
    """Strip light markdown so a caption can be used as an img alt attribute."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\[(.+?)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_]", "", text)
    return text.replace('"', "'").strip()


def convert_callouts(md, render_inner):
    """Convert blockquote admonitions (> [!type] ...) into <aside> callouts.
    render_inner(markdown) -> html renders the callout body."""
    lines, out, i = md.split("\n"), [], 0
    while i < len(lines):
        m = _CALLOUT_RE.match(lines[i])
        if m:
            ctype, i = m.group(1).lower(), i + 1
            inner = []
            while i < len(lines) and lines[i].startswith(">"):
                inner.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            html = render_inner("\n".join(inner))
            # takeaway callouts get a bold "💡 Key Takeaway:" label
            label = ('<p class="callout__label">\U0001F4A1 Key Takeaway:</p>'
                     if ctype == "insight" else "")
            out += ["", '<aside class="callout callout--%s">' % ctype, label, html,
                    "</aside>", ""]
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def convert_figures(md, render_caption):
    """Convert a standalone image line into a <figure> with italic caption.
    render_caption(markdown) -> inline html renders the caption."""
    out = []
    for line in md.split("\n"):
        m = _FIG_RE.match(line)
        if m:
            cap, src = m.group("cap"), m.group("src")
            out += ["", "<figure>",
                    '<img src="%s" alt="%s">' % (src, _plain(cap)),
                    "<figcaption>%s</figcaption>" % render_caption(cap),
                    "</figure>", ""]
        else:
            out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------
# render pipeline
# --------------------------------------------------------------------------
def make_md():
    return _md.Markdown(
        extensions=["tables", "fenced_code", "codehilite", "attr_list",
                    "md_in_html", "toc"],
        extension_configs={"codehilite": {"guess_lang": False, "css_class": "hl"}},
    )


def render_inline(text):
    html = make_md().convert(text)
    if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
        html = html[3:-4]
    return html


def render_post(text):
    """Front-matter + dialect + markdown -> (meta, body html, toc).

    Every :shepherd:/:worker:/:agent: token renders its inline logo."""
    meta, body = parse_front_matter(text)
    body = convert_figures(body, render_caption=render_inline)
    body = convert_callouts(body, render_inner=lambda s: make_md().convert(s))
    body, notes = extract_sidenotes(body)
    m = make_md()
    html = m.convert(body)
    toc = getattr(m, "toc", "")
    for idx, note in enumerate(notes):
        num = idx + 1
        sn = (
            '<span class="sn">'
            '<input type="checkbox" id="sn%d" class="sn-toggle">'
            '<label for="sn%d" class="sn-ref">%d</label>'
            '<span class="sn-body"><span class="sn-num">%d.</span> %s</span>'
            "</span>"
        ) % (num, num, num, num, render_inline(note))
        html = html.replace("@@SN%d@@" % idx, sn)
    # inline brands: :shepherd: -> hatted meta-agent logo + bold "Shepherd";
    # :worker: / :agent: -> hatless purple base-agent logo + the word.
    def _brand(cls, logo, word):
        return ('<span class="%s"><img class="brand__logo" src="../assets/%s" '
                'alt="">%s</span>' % (cls, logo, word))
    sh = _brand("brand", "logo-shepherd.png", "Shepherd")
    wk = _brand("brand brand--worker", "logo-agent.png", "worker")
    ag = _brand("brand brand--worker", "logo-agent.png", "agent")
    # always-on method marks for result tables (logo + green name, both variants)
    html = html.replace(":smark:", _brand("brand", "logo-shepherd.png", "Shepherd"))
    html = html.replace(":cro:", _brand("brand", "logo-shepherd.png", "CRO"))
    html = html.replace(":treegrpo:", _brand("brand", "logo-shepherd.png", "Tree-GRPO"))
    html = html.replace(":shepherd:", sh).replace(":worker:", wk).replace(":agent:", ag)
    return meta, html, toc


def format_date(s):
    """ISO date -> human form, e.g. 2026-06-15 -> 'June 15, 2026'. Passthrough
    on anything that does not parse."""
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").strftime("%B %-d, %Y")
    except (ValueError, TypeError):
        return s


def main():
    with open(os.path.join(_HERE, "content", "shepherd.md"), encoding="utf-8") as f:
        text = f.read()
    meta, html, toc = render_post(text)
    meta["date_display"] = format_date(meta.get("date"))
    env = Environment(loader=FileSystemLoader(os.path.join(_HERE, "templates")),
                      autoescape=False, trim_blocks=True, lstrip_blocks=True)

    tmpl = env.get_template("post.html.j2")
    blog_dir = os.path.join(_HERE, "site", "blog")
    os.makedirs(blog_dir, exist_ok=True)

    out = tmpl.render(meta=meta, body=html, toc=toc)
    with open(os.path.join(blog_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", os.path.join(blog_dir, "index.html"))

    # GitHub-README-style source page + the raw markdown it renders
    src_dir = os.path.join(_HERE, "site", "blog", "source")
    os.makedirs(src_dir, exist_ok=True)
    src_body = html.replace('src="../assets/', 'src="../../assets/')
    src_out = env.get_template("source.html.j2").render(meta=meta, body=src_body)
    with open(os.path.join(src_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(src_out)
    with open(os.path.join(src_dir, "shepherd.md"), "w", encoding="utf-8") as f:
        f.write(text)
    raw_out = env.get_template("raw.html.j2").render(meta=meta, raw=text)
    with open(os.path.join(src_dir, "raw.html"), "w", encoding="utf-8") as f:
        f.write(raw_out)
    print("wrote", os.path.join(src_dir, "index.html"))


if __name__ == "__main__":
    main()
