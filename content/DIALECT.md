# Blog markdown dialect

Reference for the markdown dialect understood by `blog/build.py`. Edit
`blog/content/shepherd.md`, rebuild, and deploy:

```bash
uv run --with markdown --with pyyaml --with jinja2 --with pygments python blog/build.py
./blog/deploy-site.sh
```

The generator reads one content file, preprocesses the custom syntax below into
HTML, runs python-markdown, and renders `blog/templates/post.html.j2` into
`blog/site/blog/index.html`. Output is deterministic (idempotent rebuilds).

## Front-matter (YAML, at top of file)

```yaml
---
title: "Shepherd: A Runtime Substrate ..."
date: "2026-06-15"
description: "One-line meta description for <head>."
authors:
  - { name: "Simon Yu",    url: "https://simonucl.github.io/", affil: 1, equal: true }
  - { name: "Weiyan Shi",  url: "https://wyshi.github.io/",    affil: 1 }
affiliations:
  - { id: 1, name: "Northeastern University" }
  - { id: 2, name: "Stanford University" }
links:
  - { label: "Paper", url: "https://arxiv.org/abs/2605.10913" }
  - { label: "X Thread (soon)" }   # no url -> rendered as muted, non-link text
---
```

The template renders the title block tmax-style: title, then authors with a
superscript `*` for `equal: true` and a superscript affiliation id, then the
affiliation line, then the resource-links row. A link with no `url` renders as
muted plain text (use for "coming soon" items).

## Sidenotes (margin "comments")

Pandoc-style inline footnote, rendered as a numbered Tufte margin note:

```markdown
A live supervisor recovers 91% of the gap.^[Read it as a proof of existence,
not a like-for-like compute win.]
```

A superscript number appears at the marker; the note text floats into the right
gutter, aligned to it, on wide screens. On narrow screens the number becomes a
tap-to-toggle control and the note expands inline. Notes are auto-numbered in
document order. The bracket matching is balanced, so a note may contain
`[links](url)`. Attach the marker directly after the anchoring punctuation, no
space before `^[`.

## Inline brand

`:shepherd:` renders the mascot logo (the hat one) followed by a bold
**Shepherd**, inline with the text:

```markdown
Once the run is data, :shepherd: needs no privileged seat.
```

Use it sparingly: a few prominent mentions per post, not every occurrence of the
name. Plain "Shepherd" / "SHEPHERD" elsewhere stays plain text.

For base/worker agents, `:worker:` and `:agent:` render the hatless purple
base-agent logo plus the word (in the worker violet), to contrast with the
hatted meta-agent. Also sparing. Append letters after the token to pluralize:
`:worker:s` renders "worker" + the logo, then "s".

For result tables, always-on method marks render the hat logo + green name:
`:smark:` -> Shepherd, `:cro:` -> CRO, `:treegrpo:` -> Tree-GRPO. Use them in
the winning row/column label so the Shepherd method stands out.

## Callouts

```markdown
> [!tldr]
> - **Problem.** ...
> - **Idea.** ...

> [!insight]
> One paragraph of takeaway.
```

`[!tldr]` renders the 📌 TL;DR box (tinted like the landing-page code blocks);
`[!insight]` renders the blue takeaway box, auto-labeled with a bold
"💡 Key Takeaway:". Content inside is normal markdown (lists, bold, inline
code). A blockquote that does NOT start with `[!type]` stays a plain blockquote.

## Figures

A line that is exactly one image becomes a `<figure>` with an italic caption
(markdown in the caption, for example bold "Figure 1.", is honored):

```markdown
![**Figure 1.** SHEPHERD makes an agent's whole execution a trace ...](../assets/fig-teaser.png)
```

Figures are vendored under `blog/site/assets/fig-*.png` and referenced with the
relative path `../assets/fig-*.png`.

## Collapsibles (FAQ, asides)

Raw HTML passes through. For the inner markdown (bold, links, lists) to render,
the tag **must** carry `markdown="1"` (md_in_html only processes children of a
flagged element); plain `<details>` leaves `**bold**` and `[links](url)` as
literal text. Keep a blank line after `<summary>` and before `</details>`:

```html
<details markdown="1">
<summary>Does it work with my model?</summary>

Yes. You write agents as typed `@shp.task` functions and **swap the model**
behind a [provider](https://docs.shepherd-agents.ai/).

</details>
```

## Table of contents and section numbering

- Put `[TOC]` on its own line where the contents box should appear (after the
  TL;DR, as in tmax). It is generated from the `##`/`###` headings.
- `##` (H2) are top-level sections, auto-numbered `1.`, `2.`, ... via CSS
  counters. `###` (H3) are subsections, numbered `N.M`.
- To leave a specific heading unnumbered, give it the class `nonum` via
  attr_list: `## Appendix {: .nonum }`.

## Code blocks

Fenced code with a language tag is syntax-highlighted (Pygments, light theme
tinted to the site palette in `blog.css`). Languages used here: `python`,
`bash`, `text` (the trace listing), `bibtex` (the citation).

## Tables

Standard GitHub pipe tables (`tables` extension). Inline markdown works inside
cells (`**bold**`, `inline code`). Escape a literal pipe in a cell as `\|`.

## Style rules (project)

- No em-dashes. Use colons, commas, parentheses, or semicolons. Middle dot `·`
  is fine in code comments.
- No "pp" in prose; spell out "percentage points" or write "from X% to Y%".
- Every number must match the source; do not fabricate. No banned words
  (primitive, trivial, "first ever", proved).
