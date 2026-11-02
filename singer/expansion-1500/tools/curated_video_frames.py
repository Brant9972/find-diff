"""Opt-in, bounded Commons video-frame *research*, never game photo approval.

Usage:
  python singer/expansion-1500/tools/curated_video_frames.py --person-id t1500_0094 --download
  python singer/expansion-1500/tools/curated_video_frames.py --person-id t1500_0094 --video-file /tmp/source.webm
Produces unapproved JPEG frames, a contact sheet and a SHA-bound manifest in --out.
No production files, state.json, or review decisions are changed.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
LEADS = ROOT / "pipeline" / "curated-video-source-leads-20261102.json"
MAX_BYTES = 80 * 1024 * 1024
SAMPLE_SECONDS = (12, 32, 52, 72, 92, 112, 132)


def allowed_video_url(url):
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.hostname == "upload.wikimedia.org"
            and parsed.path.startswith("/wikipedia/commons/")
            and parsed.path.lower().endswith(".webm")
            and not parsed.username and not parsed.password)


def select_lead(person_id):
    data = json.loads(LEADS.read_text(encoding="utf-8"))
    matches = [x for x in data["people"] if x["personId"] == person_id]
    if len(matches) != 1:
        raise ValueError("Unknown or duplicate curated personId")
    lead = matches[0]
    if (data["releaseGate"] != "SOURCE_RESEARCH_ONLY_NO_DOWNLOAD_NO_CROP_NO_LIVE"
            or lead["alreadyLive"] or lead["sourceFrameDownloaded"]
            or lead["status"] != "HOLD_CURATED_VIDEO_FRAME_EXTRACTION_AND_IDENTITY_REVIEW"
            or not lead["commonsSourcePage"].startswith("https://commons.wikimedia.org/wiki/File:")):
        raise ValueError("Not a research-only, unpublished Commons video lead")
    return lead


def commons_video_url(lead):
    # Query only the exact human-curated Commons file; never run name search.
    filename = lead["commonsSourcePage"].split("/wiki/File:", 1)[1]
    from urllib.parse import unquote
    title = "File:" + unquote(filename).replace("_", " ")
    response = requests.get("https://commons.wikimedia.org/w/api.php",
                            params={"action": "query", "format": "json", "titles": title,
                                    "prop": "videoinfo", "viprop": "url|size"}, timeout=25)
    response.raise_for_status()
    pages = response.json()["query"]["pages"]
    if len(pages) != 1:
        raise ValueError("Commons returned multiple pages")
    page = next(iter(pages.values()))
    if page.get("title", "").replace("_", " ") != title or "missing" in page:
        raise ValueError("Commons exact file title mismatch")
    info = page.get("videoinfo") or []
    if len(info) != 1:
        raise ValueError("No unique Commons video info")
    url = info[0]["url"]
    if not allowed_video_url(url):
        raise ValueError("Video URL is not on the allowlisted Wikimedia CDN")
    if info[0].get("size", MAX_BYTES + 1) > MAX_BYTES:
        raise ValueError("Video exceeds 80 MiB research limit")
    return url


def download_video(url, target):
    if not allowed_video_url(url):
        raise ValueError("Disallowed video URL")
    with requests.get(url, stream=True, timeout=(15, 45)) as response:
        response.raise_for_status()
        if not all(allowed_video_url(item.url) for item in response.history):
            raise ValueError("Unsafe redirect in video download")
        if not allowed_video_url(response.url):
            raise ValueError("Video redirected outside Wikimedia CDN")
        if int(response.headers.get("Content-Length", "0")) > MAX_BYTES:
            raise ValueError("Video exceeds download limit")
        size = 0
        with target.open("wb") as stream:
            for chunk in response.iter_content(256 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_BYTES:
                    target.unlink(missing_ok=True)
                    raise ValueError("Video exceeded streaming limit")
                stream.write(chunk)
    if size < 1024:
        target.unlink(missing_ok=True)
        raise ValueError("Empty video download")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_frames(video, output, lead, source_url):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height:format=duration",
                            "-of", "json", str(video)], capture_output=True,
                           text=True, check=True, timeout=30)
    meta = json.loads(probe.stdout)
    duration = float(meta["format"]["duration"])
    stream = meta["streams"][0]
    if duration < 10 or duration > 600 or stream["width"] < 600 or stream["height"] < 400:
        raise ValueError("Video metadata outside bounded diagnostic")
    frames = []
    for second in SAMPLE_SECONDS:
        if second >= duration - 2:
            continue
        name = "frame-%03ds.jpg" % second
        target = output / name
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-ss", str(second), "-i", str(video), "-frames:v", "1",
                        "-q:v", "3", "-y", str(target)], check=True, timeout=45)
        with Image.open(target) as img:
            img.verify()
        frames.append({"second": second, "file": name, "sha256": sha256(target),
                       "status": "PENDING_HUMAN_IDENTITY_AND_FACE_REVIEW"})
    if not frames:
        raise ValueError("No frames extracted")
    tile_w, tile_h = 440, 280
    sheet = Image.new("RGB", (tile_w * 2, tile_h * ((len(frames) + 1) // 2)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, frame in enumerate(frames):
        with Image.open(output / frame["file"]) as src:
            src.thumbnail((tile_w - 12, tile_h - 30))
            x = (i % 2) * tile_w + (tile_w - src.width) // 2
            y = (i // 2) * tile_h + 22
            sheet.paste(src.convert("RGB"), (x, y))
        draw.text(((i % 2) * tile_w + 8, (i // 2) * tile_h + 4),
                  "%s | %ds | UNVERIFIED" % (lead["personId"], frame["second"]), fill="black")
    sheet.save(output / "contact-sheet.jpg", quality=90)
    manifest = {
        "releaseGate": "RESEARCH_ONLY_NOT_APPROVED_NOT_PLAYABLE",
        "personId": lead["personId"], "name": lead["name"],
        "commonsSourcePage": lead["commonsSourcePage"], "downloadUrl": source_url,
        "originalVideoSha256": sha256(video), "durationSeconds": duration,
        "sourceCaptionIsEventAttendanceOnly": True,
        "picturedIdentityConfirmed": False, "licenseIndependentlyApproved": False,
        "gameCrop600x720": False, "fiveStagesReviewed": False,
        "eligibleForLive": False, "frames": frames,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person-id", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--video-file", type=Path)
    mode.add_argument("--download", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("/tmp/curated-video-review"))
    args = parser.parse_args()
    lead = select_lead(args.person_id)
    output = args.out.resolve() / args.person_id
    if output.is_relative_to(ROOT.parents[1]):
        raise ValueError('Review output must stay outside the Git repository')
    output.mkdir(parents=True, exist_ok=True)
    if args.download:
        url = commons_video_url(lead)
        video = output / "source.webm"
        download_video(url, video)
    else:
        video = args.video_file.resolve()
        if not video.is_file() or video.stat().st_size > MAX_BYTES:
            raise ValueError("Missing or oversized local video")
        url = "LOCAL_FILE_FROM_CURATED_COMMONS_SOURCE_UNVERIFIED"
    manifest = extract_frames(video, output, lead, url)
    print(json.dumps({"manifest": str(output / "manifest.json"),
                      "frames": len(manifest["frames"]), "status": manifest["releaseGate"]}))


if __name__ == "__main__":
    main()
