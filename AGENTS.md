# AGENTS.md — find-diff maintenance guide

This is an existing, production GitHub Pages project. **Do not recreate the game or replace live banks from stale snapshots.**

## Start here (every new conversation or agent session)
1. Confirm GitHub connector access and write permissions; never assume a previous session's credentials persist.
2. Fetch the current `main` HEAD, repository tree, and the actual current files before making edits. This document is guidance, not a substitute for inspecting code.
3. Read `singer/ELIGIBILITY.md`, relevant `singer/PROGRESS.md` notes, and existing QA scripts/workflows as applicable.
4. Scope each change to the user's current request. Other ChatGPT conversations and scheduled jobs may update this repository concurrently.
5. Never force-push, overwrite a newer JSON file with an old full copy, or attribute others' changes to yourself.

## Project
- Repository: https://github.com/Brant9972/find-diff
- Default branch: `main`
- Live game: https://brant9972.github.io/find-diff/singer/
- Live banks: `singer/questions.json` (singers), `singer/actors.json` (actors), `singer/variety.json` (variety).
- `singer/creators.json` is archived; YouTubers are **not** in the live game.
- `singer/hints.json` contains work hints; `singer/photos/` contains portraits.
- Main frontend: `singer/index.html`, `singer/game.js`, `singer/style.css`, `singer/regional-draw.js`.
- Other games/directories coexist in this repo: avoid unrelated edits.
- The repository also contains expansion plans, eligibility reviews, photo audits, tests and GitHub Actions workflows; inspect current versions rather than relying on fixed counts.

## Person records and answers
- Preserve the current schema, ID conventions, role-specific fields, attribution, and reveal coordinates. Inspect actual records before editing.
- `name` is the canonical display name; `aliases` should include established stage names, legal names and common alternative spellings. E.g. 阿信/陳信宏, Melody/殷悅, 小鐘/鐘昀呈.
- Avoid duplicate identities across and within banks; a person may legitimately appear in more than one role, but mixed-mode deduplication must remain correct.
- Prioritize artists known to Taiwan audiences; non-Taiwan artists need meaningful Taiwan recognition or notable works. Follow `singer/ELIGIBILITY.md` and the current eligibility review mechanism.
- Do not bulk add/remove people without explicit scope. If identity, suitability or rights are uncertain, quarantine/disable the item according to the current schema rather than exposing it live.

## Portrait correction procedure
1. Locate the exact person record and referenced photo path, then trace the original source and attribution.
2. Verify identity using credible source metadata; do not identify an unknown face solely by visual resemblance.
3. Prefer Wikimedia Commons/Wikipedia images with verified reuse rights, attribution and any required license conditions; avoid watermarks, poor quality, and misleading portraits.
4. If the user supplies a URL, verify the actual file page, identity label and license before using it.
5. Check whether other records share the file/path; update only intended references. Keep reveal crops and attribution accurate.
6. If no reliable replacement is available, temporarily quarantine the bad question when supported by the existing schema.
7. Check local paths, image decoding, and live image responses before calling a photo fix complete.

## Safe GitHub changes
- Read current `main` HEAD immediately before work; prefer a short-lived branch/PR for risky or multi-file edits.
- Make minimal targeted modifications. Before publishing, fetch `main` again and compare to the original HEAD. On concurrent changes, rebase/merge logically from the latest files and rerun validation; never force push.
- For Contents API updates use the current blob SHA; do not send stale SHA or replace unrelated data.
- Respect other agents and automations; report only changes actually made in this session.

## Validation and publishing
- Validate JSON parsing, unique IDs/names/aliases as appropriate, photo paths, attribution, hints and all changed references.
- Run the relevant repository QA and regression checks. In particular, preserve existing `localStorage` round/seen-history behavior when banks change; do not reset player progress unintentionally.
- Confirm that a new/edited person can appear in a playable round and their image loads (no 404).
- Inspect GitHub Actions outcomes, including any failed rights/evidence gates; don't equate a successful Pages build with every check passing.
- Verify the deployed Pages build **and** independently request/inspect the live site or asset when possible. If direct verification is unavailable, explicitly say so.
- Never report deployment or live verification as successful merely because a commit was created.

## Required change report
- What changed; exact files; people added/edited/removed.
- Commit SHA and GitHub URL.
- Separate statuses: **committed**, **deployed**, **verified live**.
- Test results and unresolved failures/limitations. If incomplete, identify the last confirmed step.

## Maintenance of this guide
- Update AGENTS.md when schema, deployment, QA, game structure, or collaboration workflow changes materially.
- Do not turn this document into a dated snapshot of counts or latest commit IDs; the current repository is the source of truth.
- A new conversation can begin with: 「接手我的猜名人・五官挑戰，先讀最新 main 與 AGENTS.md，再直接執行維護。」
