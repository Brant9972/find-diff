"""Publish review pixels and absolute immutable GitHub links, never playable banks.

Publishing has two phases: build_assets(), commit those assets, then publish_links()
with that exact commit SHA. The latter verifies every referenced blob is committed.
"""
import copy
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .core import atomic, contained, immutable_bytes, valid_reveal
from .sources import source_key

ACTIVE_CANDIDATE_STATES = {'pending_review', 'pending_evidence', 'legacy_requires_review', 'candidate_ready'}
ACTIVE_PERSON_STATES = {'pending_review', 'candidate_ready'}
STAGES = ('eyes', 'nose', 'mouth', 'chin', 'full')
STAGE_NAMES = ('眼睛', '鼻子', '嘴巴', '下巴', '全臉')
IMAGE_FORMATS = {'JPEG': ('.jpg', 'image/jpeg'), 'MPO': ('.jpg', 'image/jpeg'),
                 'PNG': ('.png', 'image/png'), 'WEBP': ('.webp', 'image/webp')}


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def _font(size):
    for path in ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _asset(root, path, blob, mime, size):
    immutable_bytes(path, blob)
    return {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(blob).hexdigest(),
            'mimeType': mime, 'width': size[0], 'height': size[1], 'bytes': len(blob)}


def _copy_image(root, input_path, output_stem, expected_hash=None):
    raw = input_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_hash and expected_hash != digest:
        raise ValueError('Source or candidate bytes changed: ' + str(input_path.relative_to(root)))
    with Image.open(io.BytesIO(raw)) as image:
        if image.width * image.height > 30_000_000:
            raise ValueError('Review source exceeds 30 megapixels')
        image.load()  # Test that the review pixels actually decode, not just the header.
        image_format = image.format
        size = image.size
        if image_format not in IMAGE_FORMATS:
            raise ValueError('Unsupported direct-review image format: ' + str(image_format))
        display_size = ImageOps.exif_transpose(image).size
    extension, mime = IMAGE_FORMATS[image_format]
    result = _asset(root, output_stem.with_suffix(extension), raw, mime, size)
    result['displayWidth'], result['displayHeight'] = display_size
    return result


def _rendered_asset(root, path, image, image_format='JPEG'):
    stream = io.BytesIO()
    image.save(stream, image_format, **({'quality': 94} if image_format == 'JPEG' else {}))
    return _asset(root, path, stream.getvalue(), 'image/jpeg' if image_format == 'JPEG' else 'image/png', image.size)


def _safe_https(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def _metadata(person, candidate):
    supplement = candidate.get('evidenceSupplement', {})
    source = supplement.get('sourceMetadata', {})
    return {
        'sourcePage': _safe_https(candidate.get('source')),
        'imageUrl': _safe_https(candidate.get('url')),
        'originalSourceUrl': _safe_https(candidate.get('originalUrl')),
        'author': candidate.get('artist') or source.get('artist'),
        'credit': candidate.get('credit') or source.get('credit'),
        'caption': candidate.get('caption') or source.get('caption'),
        'license': candidate.get('license') or source.get('license'),
        'licenseUrl': _safe_https(candidate.get('licenseUrl') or source.get('licenseUrl')),
        'externalSourceLinks': [url for url in candidate.get('externalSourceLinks', []) if _safe_https(url)],
        'originalDimensionsFromMetadata': [source.get('width'), source.get('height')],
        'rightsStatus': candidate.get('rightsStatus'),
        'identityEvidence': copy.deepcopy(candidate.get('identityEvidence')),
        'recognitionEvidence': copy.deepcopy(candidate.get('recognitionEvidence')),
        'sourceAlignmentEvidence': copy.deepcopy(candidate.get('sourceAlignmentEvidence')),
        'evidenceSupplement': copy.deepcopy(supplement),
        'warnings': copy.deepcopy(candidate.get('warnings', [])),
        'reviewerRequest': candidate.get('evidenceRequest') or person.get('chatgptReview', {}).get('reason'),
        'parentCandidateId': candidate.get('parentCandidateId'),
        'parentGameSha256': candidate.get('parentGameSha256'),
        'humanIdentityVerifiedByExporter': False,
        'humanRightsVerifiedByExporter': False,
    }


def build_assets(root, directory, state, run_id, include_retained_sources=False,
                 retained_source_person_ids=None, excluded_sources_by_person=None):
    """Build one immutable visual package after the batch, without mutating state.

    root is the singer directory. Return a deterministic manifest whose paths are
    relative to it. All active pending candidates are included, including retained
    candidates from previous batches; rejected/superseded/approved/live ones are not.
    Source-only images default to the current discovery run, preventing repeated
    re-export of old rejected-looking sources. A newly scanned person may reuse
    its already saved source-only pixels without downloading them again; other
    historical sources remain excluded. Explicit render-only mode may include
    all retained sources for a dedicated manual review.
    """
    root, directory = Path(root).resolve(), Path(directory).resolve()
    if not directory.is_relative_to(root):
        raise ValueError('Review directory must be inside singer')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,119}', str(run_id)):
        raise ValueError('Invalid visual package run ID')
    output = directory / 'review-assets' / run_id
    # Durable state can still contain an old manual source after its exact
    # Commons file page was rejected in the release plan. Do not re-export
    # those pixels as if they were fresh review leads. Never delete state.
    excluded = {
        pid: {source_key(url) for url in urls if isinstance(url, str) and url}
        for pid, urls in (excluded_sources_by_person or {}).items()
    }
    photos = []
    for person_id, person in sorted(state['people'].items()):
        if person.get('status') not in ACTIVE_PERSON_STATES:
            continue
        for candidate in sorted(person.get('candidates', []), key=lambda c: c['id']):
            if candidate.get('status') not in ACTIVE_CANDIDATE_STATES or not candidate.get('gamePath'):
                continue
            if source_key(candidate.get('source')) in excluded.get(person_id, set()):
                continue
            if not valid_reveal(candidate.get('reveal', {})):
                raise ValueError('Invalid reveal for ' + person_id + '/' + candidate['id'])
            number = len(photos) + 1
            base = output / ('photo-' + str(number).zfill(4))
            game_path = contained(root, candidate['gamePath'])
            if not candidate.get('gameSha256'):
                raise ValueError('Candidate requires a game SHA-256')
            game = _copy_image(root, game_path, base / 'candidate', candidate['gameSha256'])
            if (game['width'], game['height']) != (600, 720):
                raise ValueError('Candidate is not 600x720')
            stages = {}
            with Image.open(game_path) as image:
                image = image.convert('RGB')
                for key in STAGES:
                    x0, y0, x1, y1 = candidate['reveal'][key]
                    box = (round(x0 * image.width), round(y0 * image.height),
                           round(x1 * image.width), round(y1 * image.height))
                    mask = Image.new('RGB', image.size, '#17151f')
                    mask.paste(image.crop(box), box[:2])
                    stages[key] = _rendered_asset(root, base / (key + '.png'), mask, 'PNG')
            original = None
            if candidate.get('originalPath'):
                original = _copy_image(root, contained(root, candidate['originalPath']), base / 'source',
                                       candidate.get('originalSha256'))
            photos.append({'personId': person_id, 'name': person.get('name', ''),
                           'candidateId': candidate['id'], 'gameSha256': candidate['gameSha256'],
                           'reviewStatus': candidate['status'], 'eligibleForLive': False,
                           'candidateImage': game, 'stageImages': stages, 'sourceImage': original,
                           'reveal': copy.deepcopy(candidate['reveal']), 'metadata': _metadata(person, candidate)})
    # SOURCE-ONLY photos remain ineligible for game release until cropped and reviewed.
    manual_sources = []
    targeted_retained = set(retained_source_person_ids or ())
    for person_id, person in sorted(state['people'].items()):
        if person.get('status') in {'published', 'approved', 'duplicate_existing'}:
            continue
        for candidate in sorted(person.get('candidates', []), key=lambda c: c['id']):
            if candidate.get('status') != 'manual_crop_required' or not candidate.get('originalPath'):
                continue
            if source_key(candidate.get('source')) in excluded.get(person_id, set()):
                continue
            if (not include_retained_sources and person_id not in targeted_retained
                    and candidate.get('discoveryRunId') != run_id):
                continue
            if not candidate.get('originalSha256'):
                raise ValueError('Source-only candidate requires immutable source SHA-256')
            number = len(manual_sources) + 1
            source = _copy_image(root, contained(root, candidate['originalPath']),
                                 output / f'source-only-{number:04}' / 'original',
                                 candidate['originalSha256'])
            manual_sources.append({
                'personId': person_id, 'name': person.get('name', ''),
                'candidateId': candidate['id'], 'originalSha256': candidate['originalSha256'],
                'sourceImage': source, 'cropFailure': candidate.get('cropFailure'),
                'reviewStatus': 'SOURCE_ONLY_MANUAL_CROP_REQUIRED',
                'eligibleForLive': False, 'gameSha256': None, 'stageImages': {},
                'metadata': _metadata(person, candidate),
            })
            if len(manual_sources) >= 60:
                break
        if len(manual_sources) >= 60:
            break
    font, small_font = _font(18), _font(14)
    contacts, reveal_sheets = [], []
    for offset in range(0, len(photos), 20):
        page = photos[offset:offset + 20]
        sheet = Image.new('RGB', (960, ((len(page) + 3) // 4) * 315), '#17151f')
        draw = ImageDraw.Draw(sheet)
        entries = []
        for index, photo in enumerate(page):
            x, y = index % 4 * 240, index // 4 * 315
            draw.text((x + 7, y + 4), f"{offset + index + 1}. {photo['name']}", font=font, fill='white')
            draw.text((x + 7, y + 29), photo['personId'], font=small_font, fill='white')
            with Image.open(contained(root, photo['candidateImage']['path'])) as image:
                sheet.paste(image.convert('RGB').resize((210, 252)), (x + 15, y + 58))
            entries.append({'tile': index + 1, 'personId': photo['personId'],
                            'candidateId': photo['candidateId'], 'gameSha256': photo['gameSha256']})
        item = _rendered_asset(root, output / f'contact-sheet-{offset // 20 + 1:02}.jpg', sheet)
        item['entries'] = entries
        contacts.append(item)
    for offset in range(0, len(photos), 6):
        page = photos[offset:offset + 6]
        sheet = Image.new('RGB', (1000, 45 + len(page) * 235), '#17151f')
        draw = ImageDraw.Draw(sheet)
        for index, label in enumerate(STAGE_NAMES):
            draw.text((190 + index * 160, 10), label, font=font, fill='white')
        entries = []
        for index, photo in enumerate(page):
            y = 45 + index * 235
            draw.text((8, y + 10), photo['name'], font=font, fill='white')
            draw.text((8, y + 40), photo['personId'], font=small_font, fill='white')
            draw.text((8, y + 65), photo['candidateId'][:22], font=small_font, fill='white')
            for stage_index, key in enumerate(STAGES):
                with Image.open(contained(root, photo['stageImages'][key]['path'])) as image:
                    sheet.paste(image.convert('RGB').resize((160, 192)), (185 + stage_index * 160, y))
            entries.append({'row': index + 1, 'personId': photo['personId'],
                            'candidateId': photo['candidateId'], 'gameSha256': photo['gameSha256']})
        item = _rendered_asset(root, output / f'reveal-sheet-{offset // 6 + 1:02}.jpg', sheet)
        item['entries'] = entries
        reveal_sheets.append(item)
    manual_contacts = []
    for offset in range(0, len(manual_sources), 20):
        page = manual_sources[offset:offset + 20]
        sheet = Image.new('RGB', (960, ((len(page) + 3) // 4) * 315), '#17151f')
        draw = ImageDraw.Draw(sheet)
        entries = []
        for index, source in enumerate(page):
            x, y = index % 4 * 240, index // 4 * 315
            draw.text((x + 7, y + 4), f"{offset + index + 1}. {source['name']}",
                      font=font, fill='white')
            draw.text((x + 7, y + 29), source['personId'], font=small_font, fill='white')
            with Image.open(contained(root, source['sourceImage']['path'])) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                thumb = ImageOps.contain(image, (210, 235))
                sheet.paste(thumb, (x + 15 + (210 - thumb.width) // 2,
                                    y + 55 + (235 - thumb.height) // 2))
            draw.text((x + 7, y + 292), (source['cropFailure'] or 'Needs manual crop')[:31],
                      font=small_font, fill='#ffd183')
            entries.append({'tile': index + 1, 'personId': source['personId'],
                            'candidateId': source['candidateId'],
                            'originalSha256': source['originalSha256']})
        item = _rendered_asset(root, output / f'manual-source-sheet-{offset // 20 + 1:02}.jpg', sheet)
        item['entries'] = entries
        manual_contacts.append(item)
    manifest_path = output / 'assets-index.json'
    manifest = {'schemaVersion': 1, 'runId': run_id, 'releaseGate': 'DRAFT_ONLY_NOT_PLAYABLE',
                'assetManifestPath': str(manifest_path.relative_to(root)),
                'sourceReviewSha256': state.get('chatgptReview', {}).get('sha256'),
                'peopleCount': len({p['personId'] for p in photos}), 'photoCount': len(photos),
                'contactSheets': contacts, 'revealSheets': reveal_sheets, 'photos': photos,
                'manualSourceCount': len(manual_sources), 'manualSourcePeopleCount': len({p['personId'] for p in manual_sources}),
                'manualContactSheets': manual_contacts, 'manualSources': manual_sources}
    immutable_bytes(manifest_path, _json_bytes(manifest))
    return manifest


def _asset_objects(value):
    if isinstance(value, dict):
        if {'path', 'sha256', 'mimeType'}.issubset(value):
            yield value
        for child in value.values():
            yield from _asset_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _asset_objects(child)


def _markdown_text(value):
    text = str(value or '').replace('\n', ' ').replace('\r', ' ')
    for char in ('\\', '`', '*', '_', '[', ']', '<', '>', '#', '|'):
        text = text.replace(char, '\\' + char)
    return text


def _markdown_link(title, value):
    url = _safe_https(value)
    if not url:
        return None
    url = url.replace('>', '%3E').replace('<', '%3C').replace('\n', '%0A').replace('\r', '%0D')
    return f'[{_markdown_text(title)}](<{url}>)'


def _evidence_markdown(metadata):
    """Expose saved evidence for reviewers; never turn a name match into approval."""
    identity = metadata.get('identityEvidence')
    identity = identity if isinstance(identity, dict) else {}
    supplement = metadata.get('evidenceSupplement')
    supplement = supplement if isinstance(supplement, dict) else {}
    nodes = [identity]
    for biography in (identity.get('biography'), supplement.get('biography')):
        if isinstance(biography, dict) and biography not in nodes:
            nodes.append(biography)
    lines = ['- 身分映射：以下僅為已保存的名稱、人物資料及圖說證據，尚未目視確認照片中的人物。']
    seen = set()
    for node in nodes:
        for key, title in [('article', 'Wikipedia／人物資料頁'), ('mappingSource', '身分映射來源')]:
            link = _markdown_link(title, node.get(key))
            if link and link not in seen:
                lines.append('- ' + link)
                seen.add(link)
        for key, title in [('wikidataId', 'Wikidata ID'), ('excerpt', '人物資料摘錄'),
                           ('exactChineseAliases', '精確中文名稱對照'),
                           ('verifiedSearchAliases', '搜尋別名對照'), ('matchedAliases', '名稱相符紀錄'),
                           ('captionAliasMatches', '圖說名稱相符紀錄'), ('query', '搜尋詞'),
                           ('entityTypeEvidence', '實體類型紀錄'), ('claim', '圖片屬性紀錄'),
                           ('identityWarning', '身分證據限制')]:
            value = node.get(key)
            if value:
                if isinstance(value, list):
                    value = '、'.join(str(item) for item in dict.fromkeys(str(item) for item in value))
                entry = f'- {title}：{_markdown_text(value)}'
                if entry not in seen:
                    lines.append(entry)
                    seen.add(entry)
    external = list(metadata.get('externalSourceLinks') or [])
    external += list(identity.get('externalSourceLinks') or [])
    source = supplement.get('sourceMetadata')
    if isinstance(source, dict):
        external += list(source.get('externalSourceLinks') or [])
    credit_link = _markdown_link('署名／出處連結', metadata.get('credit'))
    if credit_link:
        lines.append('- ' + credit_link)
    for url in dict.fromkeys(value for value in external if isinstance(value, str)):
        link = _markdown_link('外部原始來源', url)
        if link:
            lines.append('- ' + link)
    lines.append('- 辨識度：尚未經 ChatGPT 目視驗證；名稱或代表作品的搜尋相符不代表玩家能辨認。')
    recognition = metadata.get('recognitionEvidence')
    if recognition:
        lines.append('- 辨識度搜尋紀錄（待核）：' + _markdown_text(json.dumps(recognition, ensure_ascii=False, sort_keys=True)))
    alignment = metadata.get('sourceAlignmentEvidence')
    if isinstance(alignment, dict) and alignment:
        lines.append('- 來源像素對應：僅表示同張照片的像素對應紀錄，不能確認人物、權利或裁切適用性。')
        for key, title in [('method', '像素對應方法'), ('matches', '特徵配對數'),
                           ('inliers', '一致配對數'), ('inlierRatio', '一致配對比例'),
                           ('sourceImageSize', '對應來源尺寸'), ('sourceSha256', '對應來源 SHA-256'),
                           ('cropBoxInParent', '舊裁切範圍'), ('cropCornersInSource', '來源裁切角點'),
                           ('note', '對應證據限制')]:
            if alignment.get(key) is not None:
                value = alignment[key]
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                lines.append(f'- {title}：{_markdown_text(value)}')
        if metadata.get('parentCandidateId'):
            lines.append('- 母候選 ID：' + _markdown_text(metadata['parentCandidateId']))
    else:
        lines.append('- 來源像素對應：尚無自動對應證據；需目視核對候選裁切與保存來源圖。')
    return lines


def publish_links(root, directory, manifest, asset_commit, repository='Brant9972/find-diff'):
    """Verify committed image bytes and publish fixed absolute image/metadata links.

    The asset SHA must already exist locally and contain every manifest/image blob.
    This prevents accidentally publishing a prior HEAD that lacks the new pixels.
    Does not commit, push, modify state or approve any candidate.
    """
    root, directory = Path(root).resolve(), Path(directory).resolve()
    if not directory.is_relative_to(root):
        raise ValueError('Review directory must be inside singer')
    if not re.fullmatch(r'[0-9a-fA-F]{40}', str(asset_commit)):
        raise ValueError('Use a full immutable 40-character asset commit SHA')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid GitHub repository identity')
    asset_commit = asset_commit.lower()
    repository_root = Path(subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], text=True).strip()).resolve()
    subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--verify', asset_commit + '^{commit}'])
    def git_path(path):
        return contained(root, path).relative_to(repository_root).as_posix()
    def urls(path):
        relative = quote(git_path(path), safe='/')
        base = f'https://github.com/{repository}/blob/{asset_commit}/{relative}'
        return {'rawUrl': f'https://raw.githubusercontent.com/{repository}/{asset_commit}/{relative}',
                'githubViewUrl': base, 'githubRawUrl': base + '?raw=true'}
    assets = list(_asset_objects(manifest))
    for item in assets:
        committed = subprocess.check_output(['git', '-C', str(root), 'cat-file', 'blob', asset_commit + ':' + git_path(item['path'])], stderr=subprocess.DEVNULL)
        if hashlib.sha256(committed).hexdigest() != item['sha256']:
            raise ValueError('Asset commit does not contain the stated bytes: ' + item['path'])
    committed_manifest = subprocess.check_output(['git', '-C', str(root), 'cat-file', 'blob', asset_commit + ':' + git_path(manifest['assetManifestPath'])], stderr=subprocess.DEVNULL)
    if committed_manifest != _json_bytes(manifest):
        raise ValueError('Asset manifest differs from the committed snapshot')
    result = copy.deepcopy(manifest)
    result['assetCommit'] = asset_commit
    result['assetManifest'] = urls(manifest['assetManifestPath'])
    for item in _asset_objects(result):
        item.update(urls(item['path']))
    result['reviewInstructions'] = [
        'These are actual committed JPEG/PNG pixels. Open rawUrl directly; githubViewUrl is a browser fallback.',
        'Review pending candidates only. Loading pixels or source metadata is not identity, recognizability or rights approval.',
        'Match decisions to personId + candidateId + gameSha256. Do not approve by list position.',
        'Write the next review to singer/expansion-1500/pipeline/chatgpt-review/latest.json on automation/celebrity-photo-pipeline.',
    ]
    lines = ['# 照片視覺審核入口', '',
             f"批次 `{manifest['runId']}`：{manifest['peopleCount']} 位人物、{manifest['photoCount']} 張現行待審圖。",
             f'所有圖片固定於資產 Commit `{asset_commit}`。沒有修改正式題庫或自動核准照片。', '',
             '請先看總覽，再開每張候選圖與五階段預覽。若圖片工具無法開啟 raw 連結，使用旁邊的 GitHub 看圖頁；無法取得像素時保留待審，不得視為已目視。', '']
    def image_line(label, item):
        return [f"![{_markdown_text(label)}]({item['rawUrl']})", '',
                f"[直接圖片]({item['rawUrl']}) · [GitHub 看圖頁]({item['githubViewUrl']}) · [GitHub 原圖]({item['githubRawUrl']})", '']
    for number, sheet in enumerate(result['contactSheets'], 1):
        lines += [f'## 照片總覽 {number}', ''] + image_line('照片總覽 ' + str(number), sheet)
    for number, sheet in enumerate(result['revealSheets'], 1):
        lines += [f'## 五階段總覽 {number}', ''] + image_line('五階段總覽 ' + str(number), sheet)
    if result.get('manualSources'):
        lines += ['## 原圖保留：尚無合格 600×720 裁切（不可當作新題）', '',
                  '以下僅是已下載的來源圖片，沒有遊戲裁切、五階段預覽或人工核准。請先核對是否真的是該人物，再判斷能否手動裁切。', '']
        for number, sheet in enumerate(result.get('manualContactSheets', []), 1):
            lines += [f'### 原圖總覽 {number}', ''] + image_line('原圖總覽 ' + str(number), sheet)
        for source in result['manualSources']:
            metadata = source['metadata']
            lines += [f"### {_markdown_text(source['name'])} · {source['personId']} · {_markdown_text(source['candidateId'])}", '',
                      f"原圖 SHA-256：{source['originalSha256']}；裁切失敗：{_markdown_text(source.get('cropFailure'))}。", '']
            lines += image_line(source['name'] + ' 待人工裁切原圖', source['sourceImage'])
            for title, key in [('來源頁', 'sourcePage'), ('授權條款', 'licenseUrl')]:
                link = _markdown_link(title, metadata.get(key))
                if link:
                    lines.append('- ' + link)
            lines += [f"- 作者：{_markdown_text(metadata.get('author') or '待確認')}",
                      f"- 授權：{_markdown_text(metadata.get('license') or '待確認')}（需人工核對）",
                      f"- 來源圖說：{_markdown_text(metadata.get('caption') or '未提供')}",
                      '- 狀態：SOURCE_ONLY；不可計入人數、不可部署。', '']
    for photo in result['photos']:
        name, cid, metadata = photo['name'], photo['candidateId'], photo['metadata']
        lines += [f"## {_markdown_text(name)} · `{photo['personId']}` · `{_markdown_text(cid)}`", '',
                  f"照片 SHA-256：`{photo['gameSha256']}`；狀態：`{photo['reviewStatus']}`。", '']
        lines += image_line(name + ' 候選照片', photo['candidateImage'])
        lines += ['| 眼睛 | 鼻子 | 嘴巴 | 下巴 | 全臉 |', '| --- | --- | --- | --- | --- |',
                  '| ' + ' | '.join(f"![{label}]({photo['stageImages'][key]['rawUrl']})" for key, label in zip(STAGES, STAGE_NAMES)) + ' |', '',
                  '五階段直接圖片：' + ' · '.join(f"[{label}]({photo['stageImages'][key]['rawUrl']})" for key, label in zip(STAGES, STAGE_NAMES)), '']
        if photo['sourceImage']:
            source = photo['sourceImage']
            lines += [f"### {_markdown_text(name)} · 已保存來源圖片", '',
                      f"下載副本 {source['width']}×{source['height']}；保留來源位元組，並非宣稱其為全尺寸原檔。", '']
            lines += image_line(name + ' 來源圖片', source)
        else:
            lines += ['來源圖片尚未保存；請核對下方來源頁，不可把候選裁切當成原圖證據。', '']
        for title, key in [('來源頁', 'sourcePage'), ('下載圖片網址', 'imageUrl'), ('原始來源網址', 'originalSourceUrl'), ('授權條款', 'licenseUrl')]:
            if metadata.get(key):
                link = _markdown_link(title, metadata[key])
                if link:
                    lines.append('- ' + link)
        lines += [f"- 作者／提供者：{_markdown_text(metadata.get('author') or '待確認')}",
                  f"- 署名／出處紀錄：{_markdown_text(metadata.get('credit') or '待確認')}",
                  f"- 授權紀錄：{_markdown_text(metadata.get('license') or '待確認')}；仍需人工核對來源是否適用。",
                  f"- 人物圖說：{_markdown_text(metadata.get('caption') or '來源未提供具名圖說，需補核')} ",
                  f"- 審核要求：{_markdown_text(metadata.get('reviewerRequest') or '核對人物、辨識度、來源權利與五階段')} ",
                  f"- 風險：{_markdown_text('；'.join(str(x) for x in metadata.get('warnings', []) if x) or '仍需獨立視覺與來源審核')}"]
        lines += _evidence_markdown(metadata) + ['']
    lines += [f"[固定資產索引 JSON]({result['assetManifest']['rawUrl']})", '',
              '請將下一輪審核結果寫入分支 `automation/celebrity-photo-pipeline` 的固定檔案 `singer/expansion-1500/pipeline/chatgpt-review/latest.json`。', '',
              '本頁只有待審成果。所有決定需綁定人物 ID、候選 ID 與照片 SHA；不得自動整合 main 或部署。', '']
    output = directory / 'review-public'
    atomic(output / 'latest.json', result)
    markdown = '\n'.join(lines)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'latest.md').write_text(markdown, encoding='utf-8')
    return result
