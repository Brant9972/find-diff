"""Self-contained offline review UI, with ID/hash-bound decision export."""
import collections
import datetime
import json
import os

from .core import atomic, contained
from .sources import now


def contact_sheets(root, out, people):
    from PIL import Image, ImageDraw, ImageFont
    from pathlib import Path
    rows = [(p, c) for p in people if p['status'] == 'pending_review' for c in p['candidates'] if c.get('gamePath') and c.get('status') in {'pending_review', 'pending_evidence', 'legacy_requires_review'}]
    font_path = next((p for p in [Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()), None)
    font = ImageFont.truetype(str(font_path), 16) if font_path else ImageFont.load_default(size=16)
    mapping, sheets = [], []
    for start in range(0, len(rows), 20):
        page = rows[start:start + 20]
        sheet = Image.new('RGB', (800, ((len(page) + 3) // 4) * 280), '#17151f')
        draw = ImageDraw.Draw(sheet)
        filename = f'contact-sheet-{start // 20 + 1:02}.jpg'
        for index, (person, candidate) in enumerate(page):
            x, y = index % 4 * 200, index // 4 * 280
            draw.text((x + 4, y + 2), person['personId'], fill='white', font=font)
            draw.text((x + 4, y + 22), person['name'], fill='white', font=font)
            try:
                with Image.open(contained(root, candidate['gamePath'])) as image:
                    image = image.convert('RGB').resize((190, 228))
                    sheet.paste(image, (x + 5, y + 50))
            except (OSError, ValueError):
                draw.text((x + 4, y + 100), 'MISSING IMAGE', fill='red', font=font)
            mapping.append({'personId': person['personId'], 'candidateId': candidate['id'], 'gameSha256': candidate.get('gameSha256'), 'sheet': filename, 'tile': index + 1})
        sheet.save(out / filename, quality=90)
        sheets.append(filename)
    atomic(out / 'contact-sheets.json', mapping)
    return sheets


def report(root, directory, state, run_id, scanned):
    out = directory / 'runs' / run_id
    out.mkdir(parents=True, exist_ok=True)
    people = list(state['people'].values())
    selected = [state['people'][pid] for pid in scanned]
    sheets = contact_sheets(root, out, people)
    failures = [{'personId': p['personId'], 'name': p['name'], 'status': p['status'], 'nextRetryAt': p.get('nextRetryAt'), 'errors': p.get('lastErrors', []), 'legacyFailure': p.get('lastFailure')} for p in people if p['status'] in {'download_failed', 'no_suitable_source', 'rejected'}]
    # Historical failureReasons below covers the entire durable roster. The
    # batch-only diagnostics must not accidentally count old failed searches.
    batch_errors = [e for p in selected for e in p.get('lastErrors', [])]
    batch_candidates = [(p, c) for p in selected for c in p.get('candidates', [])
                        if c.get('discoveryRunId') == run_id]
    provider_names = sorted({e.get('provider', 'unknown') for e in batch_errors} |
                            {c.get('provider', 'unknown') for _, c in batch_candidates} |
                            {h['provider'] for p in selected for h in p.get('history', [])
                             if h.get('provider') and h.get('time', '') >= (p.get('lastAttemptAt') or '9999')})
    provider_stages = {}
    for provider in provider_names:
        entries = [c for _, c in batch_candidates if c.get('provider', 'unknown') == provider]
        errors = [e for e in batch_errors if e.get('provider', 'unknown') == provider]
        attempted = {p['personId'] for p in selected for h in p.get('history', [])
                     if h.get('provider') == provider and h.get('time', '') >= (p.get('lastAttemptAt') or '9999')}
        provider_stages[provider] = {
            'attemptedPeople': len(attempted),
            'metadataCandidates': len(entries),
            'identitySupportedMetadata': sum(bool(c.get('identityEvidence', {}).get('captionAliasMatches') or
                                                  c.get('identityEvidence', {}).get('matchedAliases') or
                                                  c.get('identityEvidence', {}).get('claim') == 'P18') for c in entries),
            'openLicenseMetadata': sum(c.get('rightsStatus') == 'open_license_metadata' for c in entries),
            'downloadedForHumanReview': sum(c.get('status') == 'pending_review' and bool(c.get('gamePath')) for c in entries),
            'errors': dict(collections.Counter(e.get('code', 'unknown') for e in errors))}
    summary = {'runId': run_id, 'generatedAt': now(), 'scannedPeople': len(scanned),
               'peopleWithNewCandidates': sum(bool(p.get('lastRunNewCandidateIds')) for p in selected),
               'newCandidatePhotos': sum(len(p.get('lastRunNewCandidateIds', [])) for p in selected),
               'scannedWithoutCandidates': sum(not p.get('lastRunNewCandidateIds') for p in selected),
               'retryNeeded': len(failures), 'pendingReviewPeople': sum(p['status'] == 'pending_review' for p in people),
               'licenseConcernCandidates': sum(c.get('rightsStatus') == 'needs_review' for p in people for c in p['candidates'] if c.get('status') not in {'rejected','superseded'} and p['status'] != 'published'),
               'statusCounts': dict(collections.Counter(p['status'] for p in people)),
               'failureReasons': dict(collections.Counter(e['code'] for p in failures for e in p['errors'])),
               'batchFailureReasons': dict(collections.Counter(e.get('code', 'unknown') for e in batch_errors)),
               'batchProviderStages': provider_stages,
               'contactSheets': sheets, 'modifiedProduction': False, 'releaseGate': 'DRAFT_ONLY_NOT_PLAYABLE'}
    atomic(out / 'summary.json', summary)
    atomic(out / 'failures.json', failures)
    payload = {'schemaVersion': 2, 'releaseGate': 'DRAFT_ONLY_NOT_PLAYABLE', 'summary': summary, 'people': people}
    atomic(out / 'review-index.json', payload)
    def asset(path):
        return os.path.relpath(contained(root, path), out) if path else ''
    ui_people = []
    for p in people:
        row = {k: v for k, v in p.items() if k not in {'history', 'legacyRecord'}}
        row['candidates'] = [{**c, 'gameHref': asset(c.get('gamePath')), 'originalHref': asset(c.get('originalPath')), 'previewHrefs': {k: asset(v) for k,v in c.get('stagePreviews',{}).items()}} for c in p['candidates']]
        ui_people.append(row)
    # Escape '<' before embedding JSON, so untrusted captions cannot close the script element.
    encoded = json.dumps(ui_people, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    template = '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>照片候選審核</title>
<style>body{font:16px system-ui;margin:24px;background:#17151f;color:#eee}a{color:#b2dbff}select,input,button{font:inherit;padding:8px;margin:4px}article{border-top:1px solid #777;padding:20px 0}.options{display:flex;flex-wrap:wrap;gap:20px}.candidate{width:min(100%,370px);background:#292631;padding:16px;overflow-wrap:anywhere}img{max-width:100%;height:auto}.stage{display:inline-block;width:60px;height:72px;position:relative;overflow:hidden;background:#111;margin:2px}.stage img{position:absolute;width:60px;height:72px;max-width:none}.warn{color:#ffd183}details{margin:10px 0}label{display:block}textarea{width:95%;min-height:55px}pre{white-space:pre-wrap}</style>
<h1>照片候選審核</h1><p>候選圖未發布。請核對人物、辨識度、原始授權、遮擋與五階段裁切。匯出只產生審核紀錄，不會更新遊戲。</p>
<input id="search" placeholder="人物姓名／ID"><select id="filter"><option value="">全部</option><option>pending_review</option><option>rejected</option><option>download_failed</option><option>no_suitable_source</option><option>published</option><option>approved</option></select>
<input id="reviewer" placeholder="審核者名稱"><button id="export">匯出審核決定 JSON</button><p id="count"></p><main id="people"></main>
<script type="application/json" id="data">__DATA__</script><script>
const people=JSON.parse(document.querySelector('#data').textContent), decisions={};
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
function link(label,url){const n=el('a',label);try{if(new URL(url,location.href).protocol!=='https:'&&!url.startsWith('../'))return el('span',label+'（無有效連結）');n.href=url;n.target='_blank';n.rel='noopener noreferrer'}catch{}return n}
function render(){const root=document.querySelector('#people');root.replaceChildren();let count=0;
for(const p of people){if(document.querySelector('#filter').value&&p.status!==document.querySelector('#filter').value)continue;if(!(p.name+' '+p.personId).toLowerCase().includes(document.querySelector('#search').value.toLowerCase()))continue;count++;
const a=el('article');a.append(el('h2',p.name+' · '+p.personId+' · '+p.status));const options=el('div');options.className='options';
for(const c of p.candidates){const card=el('div');card.className='candidate';card.append(el('h3',c.id+' · '+c.status));
if(c.gameHref){const img=el('img');img.src=c.gameHref;img.loading='lazy';img.alt=p.name+' 候選裁切';card.append(img);const stages=el('div');for(const key of ['eyes','nose','mouth','chin','full']){const rect=c.reveal?.[key];if(!rect)continue;const box=el('span');box.className='stage';box.title=key;const im=el('img');im.src=c.gameHref;im.style.clipPath=`inset(${rect[1]*100}% ${(1-rect[2])*100}% ${(1-rect[3])*100}% ${rect[0]*100}%)`;box.append(im);stages.append(box)}card.append(stages)}
card.append(link('來源頁',c.source||''),el('span',' · '),link('原始圖片',c.url||''));if(c.originalHref){card.append(el('p'),link('已保存原圖',c.originalHref));const original=el('details');original.append(el('summary','展開原圖'));const full=el('img');full.src=c.originalHref;full.loading='lazy';full.alt=p.name+' 原圖';original.append(full);card.append(original)}
card.append(el('p',(c.artist||'作者不明')+' · '+(c.license||'授權不明')),link('授權條款',c.licenseUrl||''));const warn=el('p',(c.warnings||[]).filter(Boolean).join('；'));warn.className='warn';card.append(warn);
const detail=el('details');detail.append(el('summary','身分／代表性證據與品質結果'),el('pre',JSON.stringify({identity:c.identityEvidence,recognition:c.recognitionEvidence,requested:c.evidenceRequest,supplement:c.evidenceSupplement,validation:c.validation,rightsStatus:c.rightsStatus},null,2)));card.append(detail);
if(c.previewHrefs){const fullStages=el('details');fullStages.append(el('summary','五階段原尺寸證據'));for(const [key,url]of Object.entries(c.previewHrefs))fullStages.append(link(key,url),el('span',' · '));card.append(fullStages)}
if(!['published','approved'].includes(p.status)&&c.status!=='rejected'){const choice=el('select');for(const [v,t]of [['','尚未決定'],['rejected','退回'],['approved','人工接受']]){const o=el('option',t);o.value=v;choice.append(o)}choice.value=decisions[c.id]?.decision||'';const note=el('textarea');note.placeholder='必填：身分、辨識度、來源與裁切的審核理由';note.value=decisions[c.id]?.reason||'';const save=()=>{decisions[c.id]={personId:p.personId,candidateId:c.id,gameSha256:c.gameSha256,decision:choice.value,reason:note.value}};choice.onchange=save;note.oninput=save;card.append(choice,note)}options.append(card)}
if(!p.candidates.length)a.append(el('pre',JSON.stringify(p.lastErrors||p.lastFailure||{},null,2)));a.append(options);root.append(a)}document.querySelector('#count').textContent=count+' 位人物'}
document.querySelector('#search').oninput=render;document.querySelector('#filter').onchange=render;
document.querySelector('#export').onclick=()=>{const reviewer=document.querySelector('#reviewer').value.trim(),entries=Object.values(decisions).filter(x=>x.decision);if(!reviewer||!entries.length||entries.some(x=>!x.reason.trim()||!x.gameSha256)){alert('請填審核者、理由；沒有照片雜湊的項目不可核准。');return}const a=el('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({schemaVersion:1,reviewer,reviewedAt:new Date().toISOString(),decisions:entries},null,2)],{type:'application/json'}));a.download='review-decisions.json';a.click();URL.revokeObjectURL(a.href)};render();
</script></html>'''
    (out / 'review.html').write_text(template.replace('__DATA__', encoded), encoding='utf-8')
    if state.get('chatgptReview'):
        payload['chatgptReview']=state['chatgptReview']
        atomic(out / 'review-index.json', payload)
    atomic(directory / 'latest.json', {'runId': run_id, 'reviewIndex': str((out / 'review-index.json').relative_to(root)), 'summary': summary})
    return summary


def import_decisions(root, directory, state, document):
    """Import only explicit external review, validate the ENTIRE file before any mutation."""
    if document.get('schemaVersion') != 1 or not document.get('reviewer') or not document.get('reviewedAt'):
        raise ValueError('Review requires schemaVersion, reviewer and reviewedAt')
    reviewed_time = datetime.datetime.fromisoformat(document['reviewedAt'].replace('Z', '+00:00'))
    changes, seen = [], set()
    for entry in document.get('decisions', []):
        key = (entry['personId'], entry['candidateId'])
        if key in seen:
            raise ValueError('Duplicate review decision')
        seen.add(key)
        person = state['people'][entry['personId']]
        if person['status'] in {'approved', 'published'}:
            raise ValueError('Existing approved/published person is immutable')
        candidate = next(c for c in person['candidates'] if c['id'] == entry['candidateId'])
        if entry['decision'] not in {'approved', 'rejected'} or not entry.get('reason', '').strip():
            raise ValueError('Invalid decision or missing reason')
        if not entry.get('gameSha256') or entry['gameSha256'] != candidate.get('gameSha256'):
            raise ValueError('Review hash differs from candidate')
        image = contained(root, candidate['gamePath'])
        import hashlib
        if not image.exists() or hashlib.sha256(image.read_bytes()).hexdigest() != entry['gameSha256']:
            raise ValueError('Reviewed photo changed or missing')
        if entry['decision'] == 'approved' and candidate.get('rightsStatus') != 'open_license_metadata':
            raise ValueError('Unresolved licence: cannot import approval')
        if entry['decision'] == 'approved' and any(x[1]['decision'] == 'approved' and x[2] is person for x in changes):
            raise ValueError('Only one approved photo per person')
        changes.append((candidate, entry, person))
    archive = directory / 'reviews' / (reviewed_time.strftime('%Y%m%dT%H%M%S%f') + '.json')
    if archive.exists():
        raise ValueError('Review archive already exists; never overwrite')
    atomic(archive, document)
    for candidate, entry, person in changes:
        candidate['status'] = entry['decision']
        candidate['humanReview'] = {**entry, 'reviewer': document['reviewer'], 'reviewedAt': document['reviewedAt']}
        candidate['eligibleForLive'] = False  # integration and publication are a separate task
    for person in {id(p): p for _, _, p in changes}.values():
        person['status'] = 'approved' if any(c['status'] == 'approved' for c in person['candidates']) else ('pending_review' if any(c['status'] == 'pending_review' for c in person['candidates']) else 'rejected')
        if person['status'] == 'rejected':
            person['nextRetryAt'] = None
    atomic(directory / 'state.json', state)
