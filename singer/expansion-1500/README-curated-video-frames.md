# Curated Commons video frame diagnostic (research only)

This is an **opt-in local/runner diagnostic**, not a new provider and not a way to approve a photo. It currently supports the single curated, unpublished person `t1500_0094` 寇世勳, using `pipeline/curated-video-source-leads-20261102.json`. The 2015 CNA event description says he attended; it does **not** identify any specific frame.

Prerequisites: `ffmpeg` and `ffprobe` on PATH, plus the existing `requirements-media.txt` (Pillow and requests). Keep output **outside** the repository.

```bash
python singer/expansion-1500/tools/curated_video_frames.py \
  --person-id t1500_0094 --download --out /tmp/celebrity-video-research
# Or if the Commons API/CDN is throttled, provide a manually downloaded,
# independently source-checked WebM without repeatedly retrying:
python singer/expansion-1500/tools/curated_video_frames.py \
  --person-id t1500_0094 --video-file /tmp/cna-source.webm \
  --out /tmp/celebrity-video-research
```

The download mode queries **one exact curated Commons file** and only accepts an HTTPS `upload.wikimedia.org/wikipedia/commons/` WebM URL. If and only if the Commons metadata API responds HTTP 403, it falls back to the **exact original CDN URL pinned from the Commons file page**. The original byte size (67,245,954) and SHA-1 (`146fecdf335b2e397458422daa4be9b8007d3080`) must match the downloaded file before frame extraction. HTTP 429 still stops without bypass or retries. Maximum original size 80 MiB; stream limit and timeouts apply. There is no generic artist-name search, no automatic retry loop, and no branch commit. An HTTP 403/429 must be treated as a source-access problem, **not** as permission to scrape a different site.

The output contains seven or fewer timestamped JPEGs, `contact-sheet.jpg`, `manifest.json`, and (download mode only) `source.webm`. The manifest records the video SHA-256 and each extracted frame SHA-256. All images are marked **PENDING_HUMAN_IDENTITY_AND_FACE_REVIEW**; `eligibleForLive=false`. The script does not create a 600×720 game crop or mark any identity, license, or five-stage check approved.

Review sequence before *any* publication:
1. Verify the exact Commons file history, 2017-05-23 reviewer Daphne Lantier, Central News Agency / 張新偉 attribution, CC BY 3.0, and whether a derived screenshot is within those terms. Preserve the original source and change notice.
2. For a candidate timestamp, obtain independent **person-specific** evidence identifying who appears in that exact shot; event attendance or a video title alone is insufficient.
3. Reject multiple faces, obscured eyes/mouth, tiny face, stage projection, or blurry/unfamiliar presentation. Never use automated face detection as proof of identity.
4. Only a verified single-person source may be separately cropped to 600×720 and human-reviewed at eyes/nose/mouth/chin/full, with source and game SHA-256 recorded.
5. Check the latest main roster, aliases, QID and hints before any review PR. Run branch Mobile QA, Verify work hints, then main Pages build and public LIVE JSON QA. Never modify creators.

The script's outputs are not a release artifact. Do not copy the contact sheet or raw frames into `singer/photos/` or import this manifest as a `chatgpt-review` approval.
