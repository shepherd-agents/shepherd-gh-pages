# shepherd-agents site

Source for the SHEPHERD landing page and blog. A small Python generator renders
`content/shepherd.md` into the static site under `site/`; every push to `main`
rebuilds and deploys to GitHub Pages via `.github/workflows/pages.yml`.

## Edit / contribute
- Blog content: `content/shepherd.md` (dialect reference in `content/DIALECT.md`).
- Landing page: `site/index.html`.
- Build locally: `pip install markdown pyyaml jinja2 pygments && python build.py`,
  then open `site/index.html` (or serve `site/`).
- Open a PR; on merge to `main` the Action builds and publishes. No manual deploy.
