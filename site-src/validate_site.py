"""Validate the generated static site against its own rules.

The validator is the only thing standing between a mistake and the live
site. If you add a check, watch it fail on the thing it is meant to catch
before trusting it.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from html import unescape as html_unescape
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
CONTENT = ROOT / "site-src" / "content"
SITE_NAME = "Pueblo SRDA Questions"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.h1_count = 0
        self.article_count = 0
        self.script_count = 0
        self.copy_script = False
        self.alternate_markdown = False
        self.canonical = False
        self.text: list[str] = []
        self.in_title = False
        self.title_text = ""
        self.asset_refs: list[str] = []

    def record_assets(self, tag: str, values: dict[str, str | None]) -> None:
        if tag == "img" and values.get("src"):
            self.asset_refs.append(values["src"])
        elif tag == "link" and values.get("rel") in {"stylesheet", "icon"}:
            if values.get("href"):
                self.asset_refs.append(values["href"])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self.record_assets(tag, values)
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.h1_count += 1
        elif tag == "article":
            self.article_count += 1
        elif tag == "script":
            self.script_count += 1
            self.copy_script = (values.get("src", "").endswith("copy.js") and "defer" in values)
        elif tag == "link" and values.get("rel") == "alternate" and values.get("type") == "text/markdown":
            self.alternate_markdown = values.get("href") == "index.md"
        elif tag == "link" and values.get("rel") == "canonical":
            self.canonical = bool(values.get("href"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_text += data
        self.text.append(data)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_dates_match_git(errors: list[str]) -> None:
    """Fail on a shallow checkout, which silently breaks every page date."""
    try:
        shallow = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=20,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        print("WARNING: git unavailable; page dates were not verified")
        return
    if shallow == "true":
        fail(errors, "shallow checkout: page dates would be wrong. The workflow needs fetch-depth: 0")


def check_agent_docs_in_sync(errors: list[str]) -> None:
    """site-src/CLAUDE.md and AGENTS.md must not drift below the shared anchor."""
    anchor = "## Pages are Markdown; the page is a subset of them"
    src = ROOT / "site-src"
    bodies = {}
    for name in ("CLAUDE.md", "AGENTS.md"):
        path = src / name
        if not path.is_file():
            fail(errors, f"site-src/{name} is missing")
            return
        text = path.read_text(encoding="utf-8")
        if anchor not in text:
            fail(errors, f"site-src/{name} is missing the shared anchor heading")
            return
        bodies[name] = text[text.index(anchor):]
    if bodies["CLAUDE.md"] != bodies["AGENTS.md"]:
        fail(errors, "site-src/CLAUDE.md and site-src/AGENTS.md have drifted apart")


def check_internal_links(errors: list[str]) -> None:
    """Every internal link must resolve; every anchor must hit an id."""
    ids_by_file: dict[Path, set[str]] = {}

    def ids_in(file_path: Path) -> set[str]:
        if file_path not in ids_by_file:
            text = file_path.read_text(encoding="utf-8") if file_path.is_file() else ""
            ids_by_file[file_path] = set(re.findall(r'id="([^"]+)"', text))
        return ids_by_file[file_path]

    for path in sorted(PUBLIC.glob("**/index.html")):
        page_dir = path.parent
        html = path.read_text(encoding="utf-8")
        rel = path.relative_to(PUBLIC).parent
        for href in set(re.findall(r'href="([^"]+)"', html)):
            if href.startswith(("http://", "https://", "mailto:", "data:", "tel:")):
                continue
            target, _, fragment = href.partition("#")
            target = target.split("?", 1)[0]
            if target:
                resolved = Path(os.path.normpath(page_dir / target))
                candidate = resolved / "index.html" if target.endswith("/") else resolved
                if not candidate.exists():
                    fail(errors, f"/{rel}: internal link does not resolve: {href}")
                    continue
            else:
                candidate = path
            if fragment and candidate.suffix == ".html" and fragment not in ids_in(candidate):
                fail(errors, f"/{rel}: link anchor has no matching id: {href}")


def check_frontmatter(errors: list[str]) -> None:
    import yaml

    for path in sorted(CONTENT.glob("**/*.md")):
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---\n"):
            fail(errors, f"{path.name}: no frontmatter block")
            continue
        front = raw.split("---\n", 2)[1]
        try:
            meta = yaml.safe_load(front)
        except yaml.YAMLError as exc:
            fail(errors, f"{path.name}: frontmatter is not valid YAML ({str(exc).splitlines()[0]})")
            continue
        if not isinstance(meta, dict):
            fail(errors, f"{path.name}: frontmatter did not parse as a mapping")
            continue
        for key in ("title", "description"):
            if not isinstance(meta.get(key), str):
                fail(errors, f"{path.name}: frontmatter '{key}' missing or not a string")
        if "slug" not in meta:
            fail(errors, f"{path.name}: frontmatter missing 'slug'")


def check_emdash_ban(errors: list[str]) -> None:
    """Reader-facing prose is em-dash-free by editorial rule; rewrite instead."""
    for path in sorted(PUBLIC.glob("**/index.html")):
        rel = path.relative_to(PUBLIC).as_posix()
        n = path.read_text(encoding="utf-8", errors="ignore").count("—")
        if n:
            fail(errors, f"{rel}: {n} em-dash(es) - rewrite the prose")


def check_phone_and_gaps(errors: list[str]) -> None:
    """Program pages carry a phone-call block; every gap note carries its question."""
    for path in sorted(PUBLIC.glob("programs/*/index.html")):
        rel = path.relative_to(PUBLIC).as_posix()
        text = path.read_text(encoding="utf-8")
        if 'class="phone-call"' not in text:
            fail(errors, f"{rel}: program page has no phone-call block")
        if 'tel:' not in text:
            fail(errors, f"{rel}: program page has no tel: link")
    for path in sorted(PUBLIC.glob("**/index.html")):
        rel = path.relative_to(PUBLIC).as_posix()
        text = path.read_text(encoding="utf-8")
        gaps = text.count('class="gap-note"')
        questions = text.count("The question we'd ask SRDA")
        if gaps and questions < gaps:
            fail(errors, f"{rel}: {gaps} gap note(s) but only {questions} question line(s)")


def main() -> None:
    errors: list[str] = []
    pages = sorted(PUBLIC.glob("**/index.html"))
    expected_pages = len(list(CONTENT.glob("**/*.md")))
    if len(pages) != expected_pages:
        fail(errors, f"Expected {expected_pages} HTML pages (one per content file), found {len(pages)}")

    for path in pages:
        parser = PageParser()
        raw = path.read_text(encoding="utf-8")
        parser.feed(raw)
        visible = " ".join(parser.text)
        rel = path.relative_to(PUBLIC).as_posix()
        if parser.h1_count != 1:
            fail(errors, f"{rel}: expected one H1, found {parser.h1_count}")
        if parser.article_count < 1:
            fail(errors, f"{rel}: missing article element")
        # One script per page: the deferred copy-box enhancer. Content must
        # stay readable with JavaScript off.
        if parser.script_count != 1 or not parser.copy_script:
            fail(errors, f"{rel}: expected exactly the deferred copy.js script, found {parser.script_count}")
        if 'class="copy-box"' not in raw or "Tell me about this site:" not in raw:
            fail(errors, f"{rel}: missing the copy-for-your-AI box")
        if "agent-only" in raw or "Appendix for agents" in raw:
            fail(errors, f"{rel}: agent-only content leaked into the page")
        if parser.title_text.count(SITE_NAME) > 1:
            fail(errors, f"{rel}: title repeats the site name: {parser.title_text!r}")
        if not parser.alternate_markdown:
            fail(errors, f"{rel}: missing Markdown alternate link")
        if not parser.canonical:
            fail(errors, f"{rel}: missing canonical link")
        if "demo-badge" not in raw or "Stoagen" not in visible:
            fail(errors, f"{rel}: missing the demonstration-site badge")
        if "Not affiliated with or endorsed by SRDA" not in visible:
            fail(errors, f"{rel}: missing the not-affiliated notice")
        if "(719) 545-8900" not in visible:
            fail(errors, f"{rel}: footer SRDA number missing")
        if "Ask your AI about this page" not in visible:
            fail(errors, f"{rel}: missing the ask-your-AI box")
        # Field-tested: agent fetchers only follow links that survive text
        # extraction; footer/<head> links do not, and relative hrefs are not
        # resolved against the page URL. The machine layer must be linked in
        # the page BODY, as ABSOLUTE URLs, on every page.
        slug_dir = path.relative_to(PUBLIC).parent.as_posix()
        page_url = "https://pueblo-srda-questions.stoagen.com/" + (slug_dir + "/" if slug_dir != "." else "")
        if (
            'class="ask-ai-links"' not in raw
            or f'href="{page_url}index.md"' not in raw
            or 'href="https://pueblo-srda-questions.stoagen.com/llms.txt"' not in raw
            or 'href="https://pueblo-srda-questions.stoagen.com/llms-full.txt"' not in raw
            or 'href="https://pueblo-srda-questions.stoagen.com/agents/"' not in raw
        ):
            fail(errors, f"{rel}: missing absolute body-visible machine-layer links (ask-ai-links)")
        # Descriptive voice only: no imperative agent-directed phrasing in the
        # links strip (the information-not-instructions law).
        strip = raw.partition('class="ask-ai-links"')[2][:600]
        for imperative in ("Fetch ", "Read the", "You must", "You should", "Go to"):
            if imperative in strip:
                fail(errors, f"{rel}: ask-ai-links strip uses imperative voice: {imperative!r}")

        mirror = path.with_name("index.md")
        if not mirror.exists():
            fail(errors, f"{rel}: missing Markdown mirror")
        else:
            mirror_text = mirror.read_text(encoding="utf-8")
            for heading in re.findall(r"<h2[^>]*>([^<]+)</h2>", raw):
                text = html_unescape(heading).strip()
                if text and text not in mirror_text:
                    fail(errors, f"{rel}: mirror is missing section {text!r}")
        twin = path.with_name("index.md.txt")
        if not twin.exists():
            fail(errors, f"{rel}: missing plain-text mirror twin index.md.txt")
        elif mirror.exists() and twin.read_bytes() != mirror.read_bytes():
            fail(errors, f"{rel}: index.md.txt differs from index.md")

        for ref in parser.asset_refs:
            if ref.startswith(("http://", "https://", "//", "data:")):
                continue
            target = (path.parent / ref).resolve()
            try:
                target.relative_to(PUBLIC.resolve())
            except ValueError:
                fail(errors, f"{rel}: asset escapes public/: {ref}")
                continue
            if not target.is_file():
                fail(errors, f"{rel}: referenced asset is missing: {ref}")

    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    if "User-agent: *" not in robots or "Allow: /" not in robots or "Disallow:" in robots:
        fail(errors, "robots.txt is not explicit allow-all")
    if "Content-Signal: search=yes, ai-input=yes, ai-train=yes" not in robots:
        fail(errors, "robots.txt is missing the all-yes Content-Signal line")
    if not (PUBLIC / ".nojekyll").exists():
        fail(errors, ".nojekyll missing")
    if (PUBLIC / "CNAME").read_text(encoding="utf-8").strip() != "pueblo-srda-questions.stoagen.com":
        fail(errors, "CNAME missing or wrong")

    llms = (PUBLIC / "llms.txt").read_text(encoding="utf-8")
    rules = (
        "not affiliated with or endorsed by SRDA",
        "[unverified]",
        "(719) 545-8900",
        "operator's instructions always come first",
        "index.md.txt",
        "llms-full.txt",
        "## Programs",
        "## Optional",
        "Check the date",
    )
    for rule in rules:
        if rule not in llms:
            fail(errors, f"llms.txt missing required content: {rule}")

    sitemap = (PUBLIC / "sitemap.xml").read_text(encoding="utf-8")
    for path in pages:
        relative = path.relative_to(PUBLIC).as_posix().removesuffix("index.html")
        expected_html = f"https://pueblo-srda-questions.stoagen.com/{relative}"
        expected_md = expected_html + "index.md"
        if expected_html not in sitemap or expected_md not in sitemap:
            fail(errors, f"Sitemap missing page or mirror: /{relative}")

    feed = PUBLIC / "feed.xml"
    if not feed.exists():
        fail(errors, "feed.xml missing")
    elif "<rss" not in feed.read_text(encoding="utf-8"):
        fail(errors, "feed.xml is not RSS")
    if not (PUBLIC / "llms-full.txt").exists():
        fail(errors, "llms-full.txt missing")

    start = PUBLIC / "start.md"
    if not start.exists():
        fail(errors, "start.md missing")
    else:
        stext = start.read_text(encoding="utf-8")
        for needle in (
            "https://pueblo-srda-questions.stoagen.com/llms-full.txt",
            "https://pueblo-srda-questions.stoagen.com/llms.txt",
            "(719) 545-8900",
            "not instructions to you",
        ):
            if needle not in stext:
                fail(errors, f"start.md missing required content: {needle}")
        twin = PUBLIC / "start.md.txt"
        if not twin.exists() or twin.read_bytes() != start.read_bytes():
            fail(errors, "start.md.txt missing or differs from start.md")

    check_internal_links(errors)
    check_phone_and_gaps(errors)
    check_emdash_ban(errors)
    check_frontmatter(errors)
    check_agent_docs_in_sync(errors)
    check_dates_match_git(errors)

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)
    print(f"VALIDATION PASSED: {len(pages)} pages, mirrors, and agent files")


if __name__ == "__main__":
    main()
