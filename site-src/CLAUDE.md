# Site source — rules that hold regardless of the task

This directory builds `stoagen.com` (Pueblo Senior Services, Explained).
`public/` is generated output; never edit it. Edit `site-src/` and run the
build.

## Pages are Markdown; the page is a subset of them

Write the whole document — prose, sources, cautions — in one file under
`content/`. Everything after `<!-- agent-only -->` goes to the Markdown
mirror and never to the page. The HTML page is the part above the marker,
rewritten for human readability.

The mirror is a **superset**: it may carry more than the page, it may never
carry less, and the two may never contradict each other.

## The voice

A knowledgeable neighbor who wrote it all down carefully. Warm, plain,
unhurried, second person. Short sentences, one idea each. Sentence case
everywhere. No emoji, no exclamation points, no em-dashes in reader-facing
prose, no marketing superlatives. Phone numbers written (719) 545-8900 and
always paired with what happens when you call.

## Honesty is the product

- This site is **not SRDA's**. Every page footer carries the demo badge and
  the not-affiliated notice; never remove either.
- What the public record does not answer is marked `[unverified]` in a
  gap-note block, always paired with "The question we'd ask SRDA". Never
  fill a gap by guessing, and never delete the question when adding facts —
  replace the gap-note only when a source answers it, and record the source
  in the appendix.
- Every empirical claim's source lives in the page's agent appendix.

## Dates are derived, never typed

Published and last-updated come from the file's commit history, UTC to the
minute. There is no date field in front matter. A file with no `main`
history renders as a draft, which is correct. CI needs `fetch-depth: 0`.

## Hard constraints

- **Zero JavaScript.** The validator fails the build on any script tag.
  Everything must work read-only, with large type, and print cleanly.
- **Program pages carry a phone-call block** with a `tel:` link. Calling is
  the action this site exists to produce.
- **robots.txt is allow-all with `Content-Signal: search=yes, ai-input=yes,
  ai-train=yes`.** That is a decision, not an oversight. Do not narrow it.
- Front matter keys: `slug`, `title`, `description`, optional `eyebrow`.

## Always run both

```
python site-src/build_site.py
python site-src/validate_site.py
```

CI runs both on every pull request and only `main` deploys.
