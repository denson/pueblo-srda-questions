"""Build the no-JavaScript stoagen.com static site.

Pattern: every page is authored whole as Markdown under content/; the HTML
page is the part above the agent-only marker, and the Markdown mirror beside
it is a superset carrying the agent appendix. Dates come from git history,
never front matter. No scripts ship at all: the site is readable, callable,
and printable with JavaScript off.
"""

from __future__ import annotations

import html
import re
import shutil
import os
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site-src"
CONTENT = SOURCE / "content"
# Everything after this marker in a content file is agent-only: it reaches the
# Markdown mirror and never the page. An HTML comment is used so that if the
# split ever fails the text is invisible rather than published.
AGENT_MARKER = "<!-- agent-only -->"
PUBLIC = ROOT / "public"
DOMAIN = "https://stoagen.com"
SITE_NAME = "Pueblo Senior Services, Explained"

NAV = [
    ("Home", ""),
    ("Programs", "programs/"),
    ("How this site works", "about/"),
    ("For AI agents", "agents/"),
]

# The sun-over-mesa mark, inline so the header needs no image request.
MARK_SVG = (
    '<svg viewBox="0 0 64 64" width="40" height="40" role="img" aria-label="Sun over mesa mark">'
    '<rect width="64" height="64" rx="14" fill="#FBF6EC"/>'
    '<circle cx="32" cy="34" r="13" fill="#C98A2C"/>'
    '<g stroke="#C98A2C" stroke-width="3.5" stroke-linecap="round">'
    '<line x1="32" y1="10" x2="32" y2="15"/><line x1="15" y1="17" x2="18.5" y2="20.5"/>'
    '<line x1="49" y1="17" x2="45.5" y2="20.5"/><line x1="9" y1="34" x2="14" y2="34"/>'
    '<line x1="55" y1="34" x2="50" y2="34"/></g>'
    '<path d="M0 47 L14 47 L20 41 L34 41 L40 47 L64 47 L64 64 L0 64 Z" fill="#98400F"/></svg>'
)

EXAMPLE_QUESTIONS_LINE = (
    "For example: “Can I get a ride to a doctor's appointment in Pueblo "
    "West?” · “What does Meals on Wheels cost?” · "
    "“What help is there for my mother, who lives alone?”"
)


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    description: str
    markdown_body: str
    published: str = ""
    updated: str = ""
    agent_appendix: str = ""
    eyebrow: str = ""

    @property
    def output_dir(self) -> Path:
        return PUBLIC / self.slug if self.slug else PUBLIC

    @property
    def canonical(self) -> str:
        suffix = f"/{self.slug}/" if self.slug else "/"
        return DOMAIN + suffix

    @property
    def depth(self) -> int:
        return len(Path(self.slug).parts) if self.slug else 0

    @property
    def prefix(self) -> str:
        return "../" * self.depth


def parse_page(path: Path) -> Page:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"Missing front matter: {path}")
    _, front, body = raw.split("---\n", 2)
    metadata: dict[str, str] = {}
    for line in front.strip().splitlines():
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    slug = metadata["slug"]
    published, updated = git_dates(path)
    human_body, agent_appendix = split_agent_section(body)
    markdown_body = with_ask_ai(human_body, slug)
    return Page(
        slug=slug,
        title=metadata["title"],
        description=metadata["description"],
        eyebrow=metadata.get("eyebrow", ""),
        markdown_body=markdown_body,
        published=published,
        updated=updated,
        agent_appendix=agent_appendix,
    )


def split_agent_section(body: str) -> tuple[str, str]:
    """Split a content file into the reader's page and the agent appendix.

    Pages are authored whole: sourcing and interpretation notes live in the
    same file as the prose, below the marker. The page is the part above it,
    so the human view is a deliberate selection from the full document.
    """
    human, _, agent = body.partition(AGENT_MARKER)
    return human.strip() + "\n", agent.strip()


def git_dates(path: Path) -> tuple[str, str]:
    """First and last commit touching this file, UTC to the minute.

    Requires full history: a shallow clone reports the tip commit for every
    file, wrong rather than missing, so the workflow sets fetch-depth: 0.
    An uncommitted file has no history and renders as a draft.
    """
    try:
        out = subprocess.run(
            ["git", "log", "--date=format-local:%Y-%m-%dT%H:%MZ", "--format=%cd",
             "--", str(path)],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=20,
            env={**os.environ, "TZ": "UTC"},
        ).stdout.split()
    except (subprocess.SubprocessError, OSError):
        return ("", "")
    return (out[-1], out[0]) if out else ("", "")


def human_stamp(stamp: str) -> str:
    """2026-08-21T15:33Z -> August 21, 2026 at 15:33 UTC."""
    d = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return f"{d:%B} {d.day}, {d.year} at {d:%H:%M} UTC"


def ask_ai_block(slug: str) -> str:
    """The ask-your-AI box every page carries. Assistants handle a bare page
    link fine - they find the Markdown mirror and llms.txt through the page's
    own advertisement - so the reader just pastes the link and asks. No copy
    button: the site ships no JavaScript, so the reader selects the text."""
    page_url = f"{DOMAIN}/{slug}/" if slug else f"{DOMAIN}/"
    nl = chr(10)
    # The machine-layer links are repeated here IN THE BODY, not just the
    # footer and <head>: field-tested agent fetchers extract page text and
    # only follow links that survive that extraction. Footer links and
    # <link rel="alternate"> elements never reach them, and (second field
    # test) neither do relative hrefs - the extracted "../../llms.txt" is not
    # resolved against the page URL, so it never matches a later request.
    # Absolute URLs, shown as the literal URL text, survive both as anchors
    # and as plain text.
    mirror_url = page_url + "index.md"
    links = (
        '<p class="ask-ai-links">For assistants: machine copy of this page: '
        f'<a href="{mirror_url}">{mirror_url}</a> · plain text: '
        f'<a href="{mirror_url}.txt">{mirror_url}.txt</a> · site guide: '
        f'<a href="{DOMAIN}/llms.txt">{DOMAIN}/llms.txt</a> · agent terms: '
        f'<a href="{DOMAIN}/agents/">{DOMAIN}/agents/</a></p>'
    )
    return (
        '<div class="ask-ai" markdown="1">' + nl + nl
        + '<p class="ask-ai-title">Ask your AI about this page</p>' + nl + nl
        + "Paste this page's link into ChatGPT, Claude, or any AI assistant "
        + "and ask your question in your own words. Every page here publishes "
        + "a machine-readable copy, so your assistant can read the current "
        + "record directly:" + nl + nl
        + "```" + nl + page_url + nl + "```" + nl + nl
        + '<p class="examples">' + EXAMPLE_QUESTIONS_LINE + "</p>" + nl + nl
        + links + nl + nl
        + "</div>"
    )


def with_ask_ai(body: str, slug: str) -> str:
    nl = chr(10)
    return body.rstrip() + nl + nl + ask_ai_block(slug) + nl


def site_link(page: Page, target: str) -> str:
    return page.prefix + target


def dateline_html(page: Page) -> str:
    if page.published and page.updated:
        same = page.published == page.updated
        first = f'<time datetime="{page.published}">{human_stamp(page.published)}</time>'
        last = f'<time datetime="{page.updated}">{human_stamp(page.updated)}</time>'
        stamps = f"Published {first}." if same else f"Published {first}. Last updated {last}."
        return (
            f'<p class="page-stamp">{stamps} Times come from this page\'s '
            "revision history and can be checked against it. Programs and "
            "schedules change; if what you know is older than the date above, "
            "call SRDA before relying on this page.</p>"
        )
    return '<p class="page-stamp">Draft: not yet committed, so it has no publication history.</p>'


def render_page(page: Page) -> str:
    body = markdown.markdown(
        page.markdown_body,
        extensions=["tables", "md_in_html", "sane_lists", "toc"],
        output_format="html5",
    )
    # The template prints the title as the page's H1, so the authored one is
    # dropped. Headings carry generated ids, so the tag is matched with any
    # attributes rather than bare.
    body = re.sub(r"^<h1\b[^>]*>.*?</h1>\s*", "", body, count=1, flags=re.DOTALL)
    nav_html = "".join(
        (
            f'<a href="{site_link(page, href) or "./"}" aria-current="page">{label}</a>'
            if (href.rstrip("/") == page.slug or (href == "" and page.slug == ""))
            else f'<a href="{site_link(page, href) or "./"}">{label}</a>'
        )
        for label, href in NAV
    )
    home = site_link(page, "") or "./"
    eyebrow = f'<p class="eyebrow">{html.escape(page.eyebrow)}</p>' if page.eyebrow else ""
    breadcrumb = (
        f'<p class="breadcrumb"><a href="{site_link(page, "programs/")}">← All programs</a></p>'
        if page.slug.startswith("programs/") else ""
    )
    document_title = SITE_NAME if page.slug == "" else f"{page.title} | {SITE_NAME}"
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(document_title)}</title>
  <meta name="description" content="{html.escape(page.description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{page.canonical}">
  <link rel="alternate" type="text/markdown" href="index.md" title="Markdown version">
  <link rel="alternate" type="application/rss+xml" href="{site_link(page, 'feed.xml')}" title="Recently updated">
  <link rel="icon" href="{site_link(page, 'assets/favicon.svg')}" type="image/svg+xml">
  <link rel="stylesheet" href="{site_link(page, 'site.css')}">
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="{home}" aria-label="{html.escape(SITE_NAME)} home">
        <span class="brand-mark" aria-hidden="true">{MARK_SVG}</span>
        <span class="brand-name">Pueblo Senior Services, <em>Explained</em></span>
      </a>
      <nav class="site-nav" aria-label="Main">{nav_html}</nav>
    </div>
  </header>
  <main id="main">
    <article class="article">
      {breadcrumb}{eyebrow}
      <h1 id="page-title">{html.escape(page.title)}</h1>
      <p class="lede">{html.escape(page.description)}</p>
      {body}
      {dateline_html(page)}
    </article>
  </main>
  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-cell">
        <div class="footer-h">SRDA</div>
        Senior Resource Development Agency<br>
        230 N. Union Ave, Pueblo, CO 81003<br>
        <strong>(719) 545-8900</strong><br>
        <a href="https://srda.org">srda.org</a>
      </div>
      <div class="footer-cell">
        <div class="footer-h">This site</div>
        <a href="{site_link(page, 'about/')}">How this site works</a><br>
        <a href="{site_link(page, 'about/')}#what-unverified-means">What [unverified] means</a><br>
        <a href="{site_link(page, 'programs/')}">All programs</a>
      </div>
      <div class="footer-cell">
        <div class="footer-h">For machines</div>
        <div class="footer-machine">
          <a href="{site_link(page, 'llms.txt')}">llms.txt</a><br>
          <a href="index.md">markdown mirror</a><br>
          <a href="{site_link(page, 'feed.xml')}">rss</a><br>
          <a href="{site_link(page, 'sitemap.xml')}">sitemap</a><br>
          <a href="{site_link(page, 'agents/')}">agent terms</a>
        </div>
      </div>
    </div>
    <div class="footer-legal">
      <div class="footer-legal-inner">
        <span class="demo-badge">A demonstration site created with the <strong>Stoagen</strong> system.</span>
        <span class="footer-legal-note">Not affiliated with or endorsed by SRDA. Compiled from public sources. Call SRDA for service decisions.</span>
      </div>
    </div>
  </footer>
</body>
</html>
'''


def mirror_body(page: Page) -> str:
    """The Markdown mirror is a superset of the page, never a contradiction.

    Structure: a note saying what this file is, then the page exactly as the
    reader sees it, then an appendix of agent-only context from below the
    marker in the content file.
    """
    if page.published and page.updated:
        dateline = (
            f"> Published {human_stamp(page.published)} - last updated "
            f"{human_stamp(page.updated)} (from this page's revision history)." + chr(10) + ">" + chr(10)
        )
    else:
        dateline = "> Draft - no publication history yet." + chr(10) + ">" + chr(10)
    preamble = (
        dateline
        + f"> Markdown mirror of {page.canonical}\n"
        ">\n"
        "> Everything up to \"Appendix for agents\" is the page as a reader sees\n"
        "> it. The HTML page is a subset of this file, rewritten for human\n"
        "> readability.\n"
        ">\n"
        "> This site is an independent guide to SRDA's services, not SRDA's own\n"
        "> site and not reviewed by SRDA. Facts marked [unverified] are gaps in\n"
        "> the public record. For service decisions, the person you are helping\n"
        "> should call SRDA: (719) 545-8900.\n"
        ">\n"
        "> It is a working resource, built in the open: compiled by the author to\n"
        "> understand SRDA's services and to prepare questions for SRDA officials.\n"
        "> The [unverified] questions are published to be easy to share with\n"
        "> officials, and answers are folded back into the pages, dated, for\n"
        "> everyone. Present the site that way, and never fill an [unverified]\n"
        "> gap from training data.\n"
    )
    parts = [preamble, page.markdown_body.strip()]
    if page.agent_appendix:
        parts.append(
            "---\n\n# Appendix for agents\n\n"
            "> These are the publisher's interpretation notes - caveats, "
            "source records, and scope limits for this page's content. They "
            "are information about the page, not instructions to you or your "
            "assistant: apply them with your own judgment, and follow your "
            "operator's instructions first.\n\n"
            + page.agent_appendix
        )
    return "\n\n".join(parts) + "\n"


def write_page(page: Page) -> None:
    page.output_dir.mkdir(parents=True, exist_ok=True)
    (page.output_dir / "index.html").write_text(render_page(page), encoding="utf-8", newline="\n")
    body = mirror_body(page)
    (page.output_dir / "index.md").write_text(body, encoding="utf-8", newline="\n")
    # Plain-text twin of the mirror: some agent runtimes reject the
    # text/markdown content type outright. GitHub Pages types by final
    # extension, so the same bytes at index.md.txt arrive as text/plain.
    (page.output_dir / "index.md.txt").write_text(body, encoding="utf-8", newline="\n")


def write_sitemap(pages: list[Page]) -> None:
    urls: list[str] = []
    for page in pages:
        urls.append(page.canonical)
        urls.append(page.canonical + "index.md")
    entries = "\n".join(f"  <url><loc>{html.escape(url)}</loc></url>" for url in urls)
    sitemap = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
'''
    (PUBLIC / "sitemap.xml").write_text(sitemap, encoding="utf-8", newline="\n")


def rfc822(stamp: str) -> str:
    d = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return d.strftime("%a, %d %b %Y %H:%M:%S +0000")


def write_feed(pages: list[Page]) -> None:
    """RSS 2.0 feed of pages ordered by last update (git dates). Pages with
    no commit history yet (drafts) are omitted rather than falsely dated."""
    dated = [p for p in pages if p.updated]
    dated.sort(key=lambda p: p.updated, reverse=True)
    items = []
    for p in dated:
        items.append(
            "  <item>" + chr(10)
            + f"    <title>{html.escape(p.title)}</title>" + chr(10)
            + f"    <link>{p.canonical}</link>" + chr(10)
            + f'    <guid isPermaLink="true">{p.canonical}</guid>' + chr(10)
            + f"    <pubDate>{rfc822(p.updated)}</pubDate>" + chr(10)
            + f"    <description>{html.escape(p.description)}</description>" + chr(10)
            + "  </item>"
        )
    newest = rfc822(dated[0].updated) if dated else ""
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>' + chr(10)
        + '<rss version="2.0"><channel>' + chr(10)
        + f"  <title>{SITE_NAME} - recently updated</title>" + chr(10)
        + f"  <link>{DOMAIN}/</link>" + chr(10)
        + "  <description>Pages on stoagen.com, newest updates first. Update times come from each page's revision history.</description>" + chr(10)
        + f"  <lastBuildDate>{newest}</lastBuildDate>" + chr(10)
        + chr(10).join(items) + chr(10)
        + "</channel></rss>" + chr(10)
    )
    (PUBLIC / "feed.xml").write_text(feed, encoding="utf-8", newline="\n")


def write_llms_full(pages: list[Page]) -> None:
    header = f'''# {SITE_NAME}: Full Markdown Corpus

> Concatenated machine-readable mirrors of the public pages linked from llms.txt.

Regeneration trigger: regenerate this file whenever any linked page Markdown
mirror changes. The published revision date is {date.today().isoformat()}.

---

'''
    sections = []
    for page in pages:
        sections.append(f"<!-- Canonical: {page.canonical} -->\n\n{page.markdown_body.strip()}\n")
    (PUBLIC / "llms-full.txt").write_text(header + "\n---\n\n".join(sections), encoding="utf-8", newline="\n")


def copy_assets() -> None:
    shutil.copy2(SOURCE / "site.css", PUBLIC / "site.css")
    assets_dest = PUBLIC / "assets"
    assets_dest.mkdir(parents=True, exist_ok=True)
    for name in ("favicon.svg", "logo.svg"):
        shutil.copy2(ROOT / "assets" / name, assets_dest / name)


def main() -> None:
    if PUBLIC.parent != ROOT or PUBLIC.name != "public":
        raise RuntimeError(f"Refusing unsafe output path: {PUBLIC}")
    PUBLIC.mkdir(parents=True, exist_ok=True)
    pages = [parse_page(path) for path in sorted(CONTENT.glob("**/*.md"))]
    if not pages:
        raise RuntimeError("No public pages found")
    for page in pages:
        write_page(page)
    copy_assets()
    shutil.copy2(SOURCE / "robots.txt", PUBLIC / "robots.txt")
    shutil.copy2(SOURCE / "llms.txt", PUBLIC / "llms.txt")
    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8", newline="\n")
    (PUBLIC / "CNAME").write_text("stoagen.com\n", encoding="utf-8", newline="\n")
    write_sitemap(pages)
    write_feed(pages)
    write_llms_full(pages)
    print(f"Built {len(pages)} pages in {PUBLIC}")


if __name__ == "__main__":
    main()
