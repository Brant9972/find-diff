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
