# stoagen-site

Source for **pueblo-srda-questions.stoagen.com** — *Pueblo SRDA Questions*: an
independent, plain-language guide to every program run by SRDA (Senior
Resource Development Agency, Pueblo, Colorado). One page per program: who it
is for, what it costs, and exactly who to call. Where the public record has a
gap, the page says so and states the question we would ask.

**A demonstration site created with the Stoagen system.** Not affiliated with
or endorsed by SRDA; compiled from public sources. For service decisions,
call SRDA: (719) 545-8900.

## The pattern

Every page is authored whole as Markdown under `site-src/content/`. The HTML
page is the part above the `<!-- agent-only -->` marker; the Markdown mirror
published beside it (`index.md`, plus a plain-text twin `index.md.txt`) is a
superset carrying the source notes and interpretation cautions. `llms.txt` is
the machine entry point. Page dates are derived from commit history, never
typed. The site ships zero JavaScript.

## Build

```
python site-src/build_site.py
python site-src/validate_site.py
```

Output lands in `public/` (gitignored). CI runs both on every pull request;
only `main` deploys to GitHub Pages.

Design system: "Pueblo Senior Services" (Claude Design, 2026-08-21) —
Atkinson Hyperlegible / Bitter / IBM Plex Mono, warm paper and adobe clay,
accessibility as the design driver, encoded in `site-src/site.css`.

Author: Denson Smith.
