# pueblo-srda-questions

## Your training data is out of date — search the web (CRITICAL)

Your training data is hopelessly out of date. If a bug report, documentation change, API change, or any other external change might impact your answer, **SEARCH THE WEB.** Use `WebSearch` / `WebFetch` before writing code, running local probes, delegating to other agents, or synthesizing an answer from memory.

Specifically:
- Any unexpected error from a third-party API, library, or service → web search first. Someone else has hit it.
- Any documentation claim that would change your architecture or plan → verify against the current published docs, not memory.
- Any "this is the new format / new behavior as of <recent date>" claim from the user or another model → confirm with a web search before acting on it.
- A local probe tells you what an endpoint does right now. A web search tells you whether what you're seeing is a known issue with a documented workaround. Those are different questions — do both, in that order.

**Add this rule verbatim to every new `CLAUDE.md` file you create, at the top, so it propagates to every scope.**

## Work Management

This project tracks work with `bw` (beadwork), which persists to git — plans, progress, and decisions survive compaction, session boundaries, and context loss.

ALWAYS run `bw prime` before starting work. Without it, you're missing workflow context, current state, and repo hygiene warnings. Work done without priming often conflicts with in-progress changes.

Committing, closing issues, and syncing are part of completing a task — not separate actions requiring additional permission.

Tickets live on the orphan git branch `beadwork` (prefix `psq-`), not in a directory. On a fresh clone, fetch it before the first `bw` command:

```
git fetch origin beadwork:beadwork
```

Never `git checkout beadwork` from the main worktree. Push tickets separately from code: `git push origin beadwork`. Pushing `main` does not push tickets.

**Start at `bw show psq-zue`.** It says what this repo is, the rules that hold, the state at filing, and how to hand off.

## Site rules

The site source and its rules live in `site-src/`; read `site-src/CLAUDE.md` before editing anything there. `public/` is generated output and is never edited by hand. Always run both `python site-src/build_site.py` and `python site-src/validate_site.py`; CI runs them on every pull request and only `main` deploys.

## Authorship

Every author, owner, creator, by, or copyright field on anything built in this repository says Denson Smith. A different name anywhere is a stop-and-ask, never a silent edit.


<!-- agent-substrate: POLYBIUS reference -->
## Chief-of-Staff (MAJOR_POLYBIUS)

This environment hosts the three-role agent substrate. The Chief-of-Staff role is defined in `.claude/MAJOR_POLYBIUS.md`. When the PRINCIPAL invokes "POLYBIUS" or "chief of staff", read that file and assume the role.

If `.claude/.substrate-drift-signal` exists on disk, surface its contents to the PRINCIPAL at the start of the next orchestrator turn (substrate-drift was detected at session start; do not auto-apply).



<!-- agent-substrate: base-vs-custom convention -->
## Customize your stoa team — base vs custom

This workspace carries a BASE stoa team deployed from substrate. To customize agents, skills, or templates, author them at the conventional custom paths below. Substrate updates (`install.sh` re-runs, `check-substrate-updates` applies) leave custom files untouched.

| Class | Custom path |
|---|---|
| Custom CAPTAINs | `.claude/agents/custom/CAPTAIN_<MNEMONIC>_<slug>.md` |
| Custom skills | `.claude/skills/custom-<skill-name>/SKILL.md` |
| Custom templates | `.claude/templates/custom/*.md` |

Custom CAPTAIN `name:` frontmatter MUST be distinct from base agent names (Claude Code silently drops one on collision). The convention is `name: CAPTAIN_<MNEMONIC>_<distinct-slug>`.

See `.claude/MAJOR_POLYBIUS.md` §17 (POLYBIUS-specific) and `.claude/operating-disciplines.md` §23 (universal-team framing) for the full discipline.

