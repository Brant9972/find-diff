# 40 actor photo candidates
This folder is **pre-production only**. The source roster is `actors-pending-40/manifest.json`.
No photos are approved until a human confirms actor identity, image quality, unobstructed face,
licence/attribution and all 5 reveal zones. Public GitHub is publicly accessible regardless of
the site's intended private audience.

## Run locally with internet access
```bash
python -m pip install Pillow numpy opencv-python
python singer/photo-prep/prepare_commons_candidates.py --manifest singer/photo-prep/actors-pending-40/manifest.json --start 0 --count 10
```
Run 4 batches at --start 0, 10, 20, 30. Output defaults to actor-photo-candidates/.
Candidate photos are intentionally **not committed automatically**, and these
rough crops are **not** landmark-certified. This program uses Commons API and single-face
detection; no facial recognition or proof of celebrity identity is performed. It will miss
some faces and will misdetect others. Search misses should be reviewed manually.

## Cloud execution — no local image download required

There is now an Actions workflow at `.github/workflows/photo-prep-candidates.yml` on this branch.
It runs the existing Python download-and-crop pipeline on a GitHub-hosted computer
in four independent batches of ten. It downloads Commons 1200px thumbnails rather
than full-resolution originals for preview, applies a preliminary license filter,
and uploads per-batch `actor-photo-batch-0`, `actor-photo-batch-10`,
`actor-photo-batch-20` and `actor-photo-batch-30` artifacts.

Workflow URL:
https://github.com/Brant9972/find-diff/actions/workflows/photo-prep-candidates.yml

**Photo-specialist instruction:** Stop waiting for the chat runtime to download
originals. Use the Actions workflow. Inspect downloaded artifacts and source
metadata, verify that each portrait is genuinely the named actor, and check the
eye/nose/mouth/chin reveals. Re-search ambiguous or failed subjects. Only publish
fully identity- and rights-verified portraits to a review branch; never overwrite
the live `main` actor/game files. If an Actions job fails, inspect its log and
fix the specific failure directly instead of repeatedly asking the user to confirm
the same steps. This workflow is a *candidate collector*; results are **not**
automatically approved or installed into the game.

## Source policy changed — Wikimedia is NOT mandatory

Search for current, high-quality portraits across Wikimedia Commons **and** artist
websites, agencies, authorized press photo libraries, official interviews and event
photos, and other publicly accessible image pages. A photo source can be searched
and recorded even if its redistribution rights have not yet been established.

Record every candidate in `external-photo-sources.json` with the person's ID,
the actual photo URL, original source page, provider, photographer and rights status.
The optional GitHub Actions workflow
`.github/workflows/prepare-external-photos.yml` uses
`prepare_external_candidates.py` to download these manually researched URLs,
resize the images, and generate provisional eyes/nose/mouth/chin reveals as
**short-lived review artifacts**, *not* as public production photos.

Suggested photo selection order:
1. Artist or agency's up-to-date professional portrait accompanied by reuse terms.
2. Officially provided promotional / press photograph with permission for reposting.
3. Event or interview photographs from named photographers and sources.
4. Wikimedia Commons or other clearly licensed images when better current sources are unavailable.

Important: using an image without charging admission, keeping the URL unadvertised,
and adding attribution are **not** automatic website-publication rights. The
existing `github.io` game is publicly reachable. Keep uncertain images in the
review workflow, not the publicly accessible repository or Pages site; if rights
are unclear, look for another permitted photo or move the game to genuine private
hosting. The user should not be asked to approve every photo individually.

### Deliverables

Photo-specialist should deliver each independently verified batch without
waiting for the user to confirm routine steps:
- `id`, name, and identity evidence.
- A real person-specific image, source page, author/credit, date, license or permission.
- A visually reviewed 5-stage reveal, not just automatic face boxes.
- A prepared photo file and metadata on the photo specialist's **review branch**.
- A clear short list of failures to continue looking for, rather than blocking a
  full batch.

Do not overwrite `singer/actors.json`, `singer/questions.json`,
`singer/hints.json`, `singer/game.js` or published `singer/photos`.
