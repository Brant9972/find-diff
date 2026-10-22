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
