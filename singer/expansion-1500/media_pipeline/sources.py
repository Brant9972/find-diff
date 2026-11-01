"""Bounded, auditable source adapters. Public availability is not a licence."""
import datetime
import html
import hashlib
import ipaddress
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from functools import lru_cache

UA = 'FindDiffMediaReview/2.0 (https://github.com/Brant9972/find-diff)'
MAX_BYTES = 14_000_000


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@lru_cache(maxsize=1)
def converter():
    try:
        from opencc import OpenCC
        return OpenCC('t2s')
    except ImportError:
        return None


def norm(value):
    value = converter().convert(str(value)) if converter() else str(value)
    return re.sub(r'[\W_]+', '', unicodedata.normalize('NFKC', str(value)).casefold())


def source_key(url):
    """Canonicalize Commons file pages across path and index.php URL forms.

    The same Commons file can be linked as /wiki/File:Name.jpg or as
    /w/index.php?title=File%3AName.jpg. Human source rejections must match
    both forms, without treating an unrelated host's /wiki/File: path as
    authoritative Wikimedia metadata.
    """
    p = urllib.parse.urlsplit(str(url or ''))
    host = (p.hostname or '').casefold()
    path = urllib.parse.unquote(p.path).replace('_', ' ').casefold().rstrip('/')
    is_wikimedia = (host == 'commons.wikimedia.org' or
                    host.endswith('.wikipedia.org'))
    if is_wikimedia:
        filename = None
        if '/wiki/file:' in path:
            filename = path.split('/wiki/file:', 1)[1]
        elif path.endswith('/w/index.php'):
            title = urllib.parse.parse_qs(p.query).get('title', [''])[0]
            title = urllib.parse.unquote(title).replace('_', ' ')
            if title.casefold().startswith('file:'):
                filename = title[5:]
        if filename:
            return 'wikimedia:' + unicodedata.normalize('NFKC', filename).strip().casefold()
    return host + path + ('?' + p.query if p.query else '')


def excluded_commons_keys(person):
    """Skip explicitly rejected Commons files before exact lookup or download.

    A rejection is attached to the file page, not the performer: new photos
    remain searchable. Exact URL normalization also handles Chinese filenames
    and Commons' underscore/space variants.
    """
    return {key for url in person.get('excludedPhotoSources', [])
            if (key := source_key(url)).startswith('wikimedia:')}


def clean(value):
    # Commons extmetadata Artist/Credit often embeds MediaWiki template CSS.
    # Strip style/script *with their contents*, not just the tags: leaving
    # `.mw-parser-output {...}` in the author field corrupts attribution.
    raw = str(value or '')
    raw = re.sub(r'<\s*(style|script)\b[^>]*>.*?<\s*/\s*\1\s*>',
                 '', raw, flags=re.IGNORECASE | re.DOTALL)
    return html.unescape(re.sub('<[^>]+>', '', raw)).strip()


def identity(person, text):
    """Avoid partial matches such as 家家美食 or 黃玠瑋 for short stage names."""
    hay = str(text or '')
    hay = converter().convert(hay) if converter() else hay
    hay = unicodedata.normalize('NFKC', hay).casefold()
    prefixes = ('歌手', '歌星', '艺人', '演员', '主持人', '音乐人', '台湾', '台语', '专访')
    suffixes = ('演唱会', '演出', '专访', '访谈', '记者会', '音乐', '的', '在', '与', '照片', '肖像', '表演', '现场')
    found = []
    for alias in dict.fromkeys([person['name'], *person.get('aliases', []), *person.get('acceptedAnswers', [])]):
        key = norm(alias)
        if len(key) < 2:
            continue
        if re.fullmatch(r'[\u3400-\u9fff]{2}', key):
            for match in re.finditer(re.escape(key), hay):
                left, right = hay[:match.start()], hay[match.end():]
                if left and re.search(r'[\u3400-\u9fff]$', left) and not any(left.endswith(p) for p in prefixes):
                    continue
                if right and re.match(r'[\u3400-\u9fff]', right) and not any(right.startswith(s) for s in suffixes):
                    continue
                found.append(alias)
                break
        elif re.fullmatch(r'[a-z0-9]+', key):
            words = re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKC', str(alias)).casefold())
            pattern = r'(?<![a-z0-9])' + r'[\W_]*'.join(map(re.escape, words)) + r'(?![a-z0-9])'
            for match in re.finditer(pattern, hay) if words else ():
                # "Chapman to Fitzgerald" in a letter title uses the English
                # preposition, not actor Chapman To's surname. Keep genuine
                # "Chapman To Man-chat" and captioned performer mentions.
                if (len(words) == 2 and words[-1] == 'to' and
                        re.search(r'(?i:\b' + re.escape(words[0]) +
                                  r')\s+to\s+[A-Z]', str(text or ''))):
                    continue
                # A suffix of a hyphenated given name is a different person.
                prefix = hay[:match.start()]
                if len(words) >= 2 and len(prefix) > 1 and prefix.endswith('-') and prefix[-2].isalnum():
                    continue
                found.append(alias)
                break
        elif key in norm(text):
            found.append(alias)
    return found


def identity_key(person):
    return tuple(sorted({norm(value) for value in [person['name'], *person.get('acceptedAnswers', [])]}))


def verified_identity(person, http):
    """Per-person HTTP context; only the Q5/exact-name resolver may populate it."""
    return getattr(http, 'verified_identities', {}).get(identity_key(person))


def phrase_query(value):
    # Commons search otherwise treats a romanized name as independent tokens.
    return '"' + str(value).replace('"', ' ').strip() + '" filetype:bitmap'


def disputed_license_source(candidate):
    """VOGUE Taiwan video stills have an independently documented rights conflict.

    Wikimedia Foundation Legal reported in March 2025 that Condé Nast said
    VOGUE Taiwan's YouTube CC settings were erroneous and its videos were not
    authorized for reuse. Do not rely on the Commons CC metadata for these.
    https://commons.wikimedia.org/wiki/Commons:Village_pump/Archive/2025/03
    """
    text = ' '.join(str(candidate.get(key, '')) for key in
                    ('artist', 'credit', 'caption', 'filename', 'source'))
    return bool(re.search(r'vogue[\s._-]*taiwan|vogue[\s._-]*臺灣|vogue[\s._-]*台灣|(?:台灣|臺灣)版?\s*vogue', text, re.I))



def commons_review_status(page):
    """Detect explicit Commons licence-review flags; absence is NOT approval.

    Commons can advertise CC BY metadata while the file is still in the hidden
    "License review needed" category (e.g. am730 video stills). Do not
    download such sources until the review is independently resolved.
    """
    categories = {norm(row.get('title', '')) for row in page.get('categories', [])}
    if 'categorylicensereviewfailed' in categories:
        return 'failed'
    if 'categorylicensereviewneeded' in categories:
        return 'needed'
    return 'not_flagged' if 'categories' in page else 'not_checked'


def rights(candidate):
    """Conservative machine eligibility, never a final legal or human approval."""
    if disputed_license_source(candidate):
        return 'rights_disputed'
    if candidate.get('licenseReviewStatus') == 'failed':
        return 'rights_disputed'
    if candidate.get('licenseReviewStatus') == 'needed':
        return 'needs_review'
    name = candidate.get('license', '').strip().casefold().replace('_', '-')
    url = candidate.get('licenseUrl', '')
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname not in {'creativecommons.org', 'www.creativecommons.org'}:
        return 'needs_review'
    path = p.path.rstrip('/')
    for code in ('by', 'by-sa'):
        if re.fullmatch(r'/licenses/' + code + r'/(1\.0|2\.0|2\.5|3\.0|4\.0)(?:/[^/]+)?', path):
            version = path.split('/')[3]
            if name in {f'cc {code} {version}', f'{code}-{version}'} and candidate.get('artist'):
                return 'open_license_metadata'
    if path.startswith('/publicdomain/zero/1.0') and name in {'cc0', 'cc0 1.0', 'cc0-1.0'}:
        return 'open_license_metadata'
    return 'needs_review'


class SourceError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def public_https(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise SourceError('unsafe_url', 'Only public HTTPS URLs without credentials are accepted')
    host = p.hostname.lower()
    if host == 'localhost' or host.endswith(('.local', '.internal')):
        raise SourceError('unsafe_url', 'Private destinations are not accepted')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise SourceError('unsafe_url', 'Private IP destinations are not accepted')
    except ValueError:
        pass
    return host


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, deadline=None):
        super().__init__()
        self.deadline = deadline

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_https(newurl)
        if self.deadline is not None:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise SourceError('time_budget', 'Redirect exceeded request deadline')
            req.timeout = min(getattr(req, 'timeout', remaining), remaining)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HTTP:
    def __init__(self, attempts=3, interval=.8, budget=None, timeout=20, blocked_hosts=None):
        self.attempts, self.interval, self.budget = max(1, min(3, attempts)), interval, budget
        self.last = {}
        self.timeout = max(.01, timeout)
        self.denied_hosts = set()
        # A single Wikimedia thumbnail can return 403 while another file on
        # the same upload host is accessible. Keep these refusals URL-scoped;
        # a 429 or a proxy-level refusal still blocks the whole host.
        self.blocked_upload_urls = set()
        # May be shared by concurrent workers. Each worker still owns its time budget.
        self.blocked_hosts = blocked_hosts if blocked_hosts is not None else {}
        self.verified_identities = {}
        self.openverse_results = {}
        # CirrusSearch overload is not a host-wide HTTP refusal. Keep its circuit
        # separate so exact-title and prefix metadata lookups remain usable.
        self.search_busy_until = {}

    def _seconds_left(self, deadline):
        if self.budget is not None and time.monotonic() >= self.budget:
            raise SourceError('time_budget', 'Person/provider time budget reached')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SourceError('network_error', 'Per-request wall time budget reached')
        return remaining

    def _pause(self, delay, deadline):
        if delay <= 0:
            return
        if delay >= self._seconds_left(deadline):
            raise SourceError('time_budget', 'Insufficient budget for source backoff; moving on')
        time.sleep(delay)

    def _refusal(self, host):
        refusal = self.blocked_hosts.get(host)
        if refusal and (refusal.get('until') is None or time.monotonic() < refusal['until']):
            raise SourceError(refusal['code'], refusal['reason'])
        if host in self.denied_hosts:
            raise SourceError('proxy_access_denied', 'Proxy denied this host in this batch')

    def _retry_after(self, headers, default=60):
        value = headers.get('Retry-After', str(default))
        try:
            return max(1, min(float(value), 3600))
        except (TypeError, ValueError):
            try:
                return max(1, min((parsedate_to_datetime(value) - datetime.datetime.now(datetime.timezone.utc)).total_seconds(), 3600))
            except (TypeError, ValueError):
                return default

    def get(self, url, params=None, allow_wikimedia_original_retry=False):
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        host = public_https(url)
        if host == 'upload.wikimedia.org' and url in self.blocked_upload_urls:
            raise SourceError('http_403', 'This exact Wikimedia upload URL refused earlier in the batch')
        # Commons thumbnail and original URLs often share upload.wikimedia.org.
        # A 403 on one thumbnail path must not make the *one* original-file
        # fallback unreachable. Never bypass a 429, proxy refusal, or any
        # unrelated host; this opt-in is used only after a thumbnail 403.
        if allow_wikimedia_original_retry and host != 'upload.wikimedia.org':
            raise SourceError('invalid_fallback', 'Only Wikimedia originals may bypass a thumbnail 403')
        bypass_refusal = (allow_wikimedia_original_retry and
                          self.blocked_hosts.get(host, {}).get('code') == 'http_403')
        blocked = self.blocked_hosts.get(host)
        if blocked and blocked.get('code') == 'source_api_busy' and blocked.get('until'):
            remaining = blocked['until'] - time.monotonic()
            if remaining > 0:
                if self.budget is not None and time.monotonic() + remaining + 1 >= self.budget:
                    raise SourceError('source_api_busy', 'Commons busy; preserve retry status until cooldown expires')
                time.sleep(remaining + 0.25)
        if not bypass_refusal:
            self._refusal(host)
        # Retries share one wall budget; slow downloads cannot multiply socket timeout by attempts.
        deadline = time.monotonic() + self.timeout
        if self.budget is not None:
            deadline = min(deadline, self.budget)
        self._seconds_left(deadline)
        for attempt in range(self.attempts):
            if not bypass_refusal:
                self._refusal(host)
            self._pause(max(0, self.interval - (time.monotonic() - self.last.get(host, 0))), deadline)
            try:
                timeout = self._seconds_left(deadline)
                with urllib.request.build_opener(HTTPSRedirect(deadline)).open(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=timeout) as response:
                    if int(response.headers.get('Content-Length', '0')) > MAX_BYTES:
                        raise SourceError('oversize', 'Response exceeds 14 MB')
                    data = bytearray()
                    read_chunk = getattr(response, 'read1', response.read)
                    while True:
                        remaining = self._seconds_left(deadline)
                        connection = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
                        if connection is not None:
                            connection.settimeout(remaining)
                        chunk = read_chunk(min(65536, MAX_BYTES + 1 - len(data)))
                        if not chunk:
                            break
                        data.extend(chunk)
                        if len(data) > MAX_BYTES:
                            raise SourceError('oversize', 'Response exceeds 14 MB')
                    self.blocked_hosts.pop(host, None)
                    return bytes(data)
            except urllib.error.HTTPError as exc:
                if exc.code in {403, 429}:
                    if exc.code == 403 and host == 'upload.wikimedia.org':
                        # A denied thumb path is not evidence that all other
                        # Commons images (or its original) are inaccessible.
                        self.blocked_upload_urls.add(url)
                    else:
                        self.blocked_hosts[host] = {'code': 'http_' + str(exc.code),
                            'reason': 'Source refused/rate-limited this batch: ' + str(exc),
                            'until': time.monotonic() + self._retry_after(exc.headers) if exc.code == 429 else None}
                    raise SourceError('http_' + str(exc.code), str(exc)) from exc
                if exc.code not in {500, 502, 503, 504} or attempt + 1 == self.attempts:
                    raise SourceError('http_' + str(exc.code), str(exc)) from exc
                self._pause(min(self._retry_after(exc.headers, 2), 2), deadline)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if 'Tunnel connection failed: 403' in str(exc):
                    self.denied_hosts.add(host)
                    self.blocked_hosts[host] = {'code': 'proxy_access_denied', 'reason': str(exc), 'until': None}
                    raise SourceError('proxy_access_denied', str(exc)) from exc
                previous = self.blocked_hosts.get(host, {})
                failures = previous.get('failures', 0) + 1
                if attempt + 1 == self.attempts:
                    self.blocked_hosts[host] = {'code': 'network_error', 'reason': str(exc),
                        'until': time.monotonic() + 30 if failures >= 2 else time.monotonic(), 'failures': failures}
                    raise SourceError('network_error', str(exc)) from exc
                self._pause(2 ** attempt, deadline)
            finally:
                self.last[host] = time.monotonic()
        raise SourceError('network_error', 'Request attempts exhausted')

    def json(self, url, **params):
        is_search = params.get('generator') == 'search' or params.get('list') == 'search'
        if is_search and self.search_busy_until.get(public_https(url), 0) > time.monotonic():
            raise SourceError('source_api_busy', 'CirrusSearch cooling down; use a non-search lookup')
        try:
            data = json.loads(self.get(url, params or None))
        except (ValueError, UnicodeError) as exc:
            raise SourceError('invalid_metadata', 'Source returned invalid JSON') from exc
        if isinstance(data, dict) and data.get('error'):
            error = data['error']
            code = str(error.get('code', 'unknown'))
            message = code + ': ' + str(error.get('info', error))[:300]
            if code in {'cirrussearch-too-busy-error', 'maxlag', 'readonly'}:
                host = public_https(url)
                if code == 'cirrussearch-too-busy-error':
                    self.search_busy_until[host] = time.monotonic() + 30
                else:
                    self.blocked_hosts[host] = {'code': 'source_api_busy', 'reason': message,
                        'until': time.monotonic() + 30}
                raise SourceError('source_api_busy', message)
            raise SourceError('source_api_error', message)
        return data


class Wikimedia:
    name = 'wikimedia'

    def search(self, person, http, round_number=0):
        queries = list(dict.fromkeys([person['name'], person.get('preferredImageQuery') or person['name'], *person.get('photoSearchKeywords', []), *person.get('aliases', [])]))
        # Rotating query order gives retries new searches even with a bounded candidate budget.
        shift = round_number % len(queries)
        queries = queries[shift:] + queries[:shift]
        articles, qids, files = {}, set(), set()
        for lang in ('zh', 'en'):
            titles = [person['name'], *person.get('aliases', [])]
            for title in titles[:2]:
                data = http.json(f'https://{lang}.wikipedia.org/w/api.php', action='query', format='json', formatversion=2,
                                 titles=title, redirects=1, converttitles=1, prop='pageimages|pageprops|extracts|info|images',
                                 imlimit=50, piprop='name', pilicense='free', exintro=1, explaintext=1, inprop='url')
                for page in data.get('query', {}).get('pages', []):
                    intro = page.get('extract', '')
                    if page.get('missing') or 'disambiguation' in page.get('pageprops', {}) or not identity(person, intro):
                        continue
                    qid = page.get('pageprops', {}).get('wikibase_item')
                    if qid:
                        qids.add(qid)
                    evidence = {'article': page.get('fullurl', ''), 'excerpt': intro[:1200], 'matchedAliases': identity(person, intro), 'wikidataId': qid}
                    names = [page.get('pageimage')] + [x.get('title', '').removeprefix('File:') for x in page.get('images', []) if identity(person, x.get('title', ''))]
                    for filename in filter(None, names):
                        articles[filename] = evidence
        for qid in sorted(qids):
            data = http.json(f'https://www.wikidata.org/wiki/Special:EntityData/{qid}.json')
            claims = data.get('entities', {}).get(qid, {}).get('claims', {})
            for claim in claims.get('P18', []):
                filename = claim.get('mainsnak', {}).get('datavalue', {}).get('value')
                if isinstance(filename, str):
                    articles.setdefault(filename, {'article': f'https://www.wikidata.org/wiki/{qid}', 'wikidataId': qid, 'claim': 'P18', 'identityWarning': 'Article/entity match is not visual identity verification'})
        # Also search Commons directly, rather than only the selected article portrait.
        for query in queries[:2]:
            data = http.json('https://commons.wikimedia.org/w/api.php', action='query', format='json', formatversion=2,
                             generator='search', gsrsearch=query + ' filetype:bitmap', gsrnamespace=6, gsrlimit=10,
                             gsroffset=(round_number % 3) * 10)
            for page in data.get('query', {}).get('pages', []):
                articles.setdefault(page.get('title', '').removeprefix('File:'), {'query': query, 'identityWarning': 'Search result only; identity needs review'})
        for filename, evidence in articles.items():
            if filename in files or not re.search(r'\.(jpg|jpeg|png|webp)$', filename, re.I):
                continue
            files.add(filename)
            data = http.json('https://commons.wikimedia.org/w/api.php', action='query', format='json', formatversion=2,
                             titles='File:' + filename, prop='imageinfo|categories', clcategories='Category:License review needed|Category:License review failed', cllimit=10, iiprop='url|extmetadata|size', iiurlwidth=1400)
            for page in data.get('query', {}).get('pages', []):
                for info in page.get('imageinfo', []):
                    ext = info.get('extmetadata', {})
                    val = lambda key: clean(ext.get(key, {}).get('value', ''))
                    # Legacy Wikimedia article/P18 adapter must normalize the
                    # Commons HTTP CC metadata URL just like CommonsSearch.
                    # This is metadata canonicalization, NOT rights approval.
                    license_url = val('LicenseUrl')
                    if license_url.startswith('http://creativecommons.org/'):
                        license_url = 'https://' + license_url[7:]
                    yield {'provider': self.name, 'url': info.get('thumburl') or info.get('url', ''), 'originalUrl': info.get('url', ''),
                           'downloadVariant': 'wikimedia_thumbnail_1400' if info.get('thumburl') else 'original', 'source': info.get('descriptionurl', ''),
                           'filename': filename, 'artist': val('Artist'), 'credit': val('Credit'),
                           'license': val('LicenseShortName'), 'licenseUrl': license_url,
                           'caption': val('ImageDescription'), 'licenseReviewStatus': commons_review_status(page), 'identityEvidence': evidence,
                           'recognitionEvidence': {'representativeWorks': person.get('representativeWorks', []), 'matchedWorks': [w for w in person.get('representativeWorks', []) if isinstance(w, str) and norm(w) in norm(filename + ' ' + val('ImageDescription'))], 'note': 'Search context only; recognizability not verified'},
                           'searchTime': now(), 'width': info.get('width'), 'height': info.get('height')}


class Openverse:
    name = 'openverse'

    def search(self, person, http, round_number=0):
        context = verified_identity(person, http)
        aliases = context['englishAliases'] if context and context['englishAliases'] else [person['name'], *person.get('aliases', [])]
        query = aliases[round_number % len(aliases)]
        cache = getattr(http, 'openverse_results', None)
        if cache is None:
            http.openverse_results = cache = {}
        key = (query, 1 + round_number % 3)
        if key not in cache:
            cache[key] = http.json('https://api.openverse.org/v1/images/', q=query, page_size=20, page=key[1], license_type='commercial,modification')
        data = cache[key]
        for row in data.get('results', []):
            code, version = row.get('license', ''), row.get('license_version', '')
            filename = urllib.parse.unquote(urllib.parse.urlsplit(row.get('url', '')).path.rsplit('/', 1)[-1])
            evidence = {'query': query, 'identityWarning': 'Search match only; verify original page and pictured person'}
            if context:
                evidence.update(context['evidence'])
                evidence['matchedAliases'] = identity({**person, 'aliases': context['aliases']}, filename + ' ' + row.get('title', ''))
            yield {'provider': self.name, 'url': row.get('url', ''), 'source': row.get('foreign_landing_url', ''),
                   'filename': filename,
                   'artist': row.get('creator', ''), 'license': 'CC ' + code.upper() + ' ' + version if code != 'cc0' else 'CC0',
                   'licenseUrl': row.get('license_url', ''), 'caption': row.get('title', ''),
                   'identityEvidence': evidence,
                   'recognitionEvidence': {'note': 'Not visually verified'}, 'searchTime': now(),
                   'rightsWarning': 'Aggregator metadata; original source licence must be checked by reviewer'}



class CuratedCommons:
    """Bounded original-file fallback for human-verified Commons file pages.

    This avoids relying on transient Commons search/imageinfo when a reviewer
    already checked the original file's caption, uploader and licence page.
    It does NOT approve the image: the normal rights, crop, face, dedupe and
    five-stage human-review gates still apply. All URLs are strict allowlists.
    """
    name = 'curated'

    def search(self, person, http, round_number=0):
        excluded = excluded_commons_keys(person)
        exact = {norm(str(name).removeprefix('File:'))
                 for name in person.get('reviewExactCommonsFiles', [])[:3]}
        for item in person.get('reviewVerifiedOriginalSources', [])[:3]:
            filename = str(item.get('filename', '')).strip()
            source = str(item.get('source', '')).strip()
            if source_key(source) in excluded:
                continue
            url = str(item.get('url', '')).strip()
            src = urllib.parse.urlsplit(source)
            original = urllib.parse.urlsplit(url)
            src_path = urllib.parse.unquote(src.path).replace('_', ' ')
            file_path = urllib.parse.unquote(original.path)
            if not filename or norm(filename) not in exact:
                continue
            if (src.scheme != 'https' or src.hostname != 'commons.wikimedia.org'
                    or not src_path.startswith('/wiki/File:')
                    or norm(src_path.split('/wiki/File:', 1)[1]) != norm(filename)
                    or src.query or src.fragment):
                continue
            # Wikimedia hashes the underscore-normalized filename into two
            # path segments. Validate the COMPLETE path, not just its suffix:
            # a malicious or unrelated image must never inherit a Commons
            # caption/license merely because its basename looks similar.
            canonical = filename.replace(' ', '_')
            digest = hashlib.md5(canonical.encode('utf-8')).hexdigest()
            original_path = f'/wikipedia/commons/{digest[0]}/{digest[:2]}/{canonical}'
            allowed_thumbs = {
                f'/wikipedia/commons/thumb/{digest[0]}/{digest[:2]}/{canonical}/{width}px-{canonical}'
                for width in (960, 1400)
            }
            is_thumbnail = file_path in allowed_thumbs
            if (original.scheme != 'https'
                    or original.hostname != 'upload.wikimedia.org'
                    or file_path not in ({original_path} | allowed_thumbs)
                    or original.query or original.fragment):
                continue
            # A Commons page can also carry a human-reviewed CC licence for
            # a YouTube still. This is NOT equivalent to arbitrary YouTube
            # footage or to a licence string supplied by a search result.
            # Require an exact Commons file, hashed Wikimedia original URL,
            # named author, a dated independent Commons licence reviewer and
            # the exact 11-character source video identifier. The caller's
            # curated record must have been checked against that Commons page.
            source_type = item.get('sourceType')
            own_work = source_type == 'uploader_own_work'
            youtube = urllib.parse.urlsplit(str(item.get('originalSourceUrl', '')))
            youtube_params = urllib.parse.parse_qs(youtube.query, strict_parsing=False)
            reviewed_youtube = (
                source_type == 'commons_youtube_cc_reviewed'
                and youtube.scheme == 'https'
                and youtube.hostname in {'www.youtube.com', 'youtube.com'}
                and youtube.path == '/watch'
                and not youtube.fragment and not youtube.username
                and set(youtube_params) == {'v'}
                and len(youtube_params.get('v', [])) == 1
                and bool(re.fullmatch(r'[A-Za-z0-9_-]{11}', youtube_params['v'][0]))
                and item.get('license') == 'CC BY 3.0'
                and str(item.get('licenseUrl', '')).rstrip('/')
                    == 'https://creativecommons.org/licenses/by/3.0'
                and bool(str(item.get('licenseReviewer', '')).strip())
                and bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',
                                      str(item.get('licenseReviewedAt', ''))))
            )
            if (not item.get('artist') or not item.get('caption')
                    or not (own_work or reviewed_youtube)
                    or item.get('verificationUrl') != source
                    or not item.get('verifiedAt')
                    or not identity(person, item['caption'])):
                continue
            candidate = {
                'provider': 'commons', 'source': source, 'url': url,
                'originalUrl': ('https://upload.wikimedia.org' + urllib.parse.quote(original_path, safe='/')
                                if is_thumbnail else url),
                'downloadVariant': ('wikimedia_thumbnail_curated' if is_thumbnail else 'original'),
                'filename': filename,
                'caption': item['caption'], 'artist': item['artist'],
                'license': item.get('license', ''),
                'licenseUrl': item.get('licenseUrl', ''),
                'licenseReviewStatus': 'reviewed' if reviewed_youtube else 'not_checked',
                'identityEvidence': {
                    'curatedOriginalMetadataOnly': True,
                    'commonsYouTubeLicenseReview': ({
                        'originalSourceUrl': item['originalSourceUrl'],
                        'reviewer': item['licenseReviewer'],
                        'reviewedAt': item['licenseReviewedAt'],
                    } if reviewed_youtube else None),
                    'verifiedAt': item['verifiedAt'],
                    'verificationUrl': source,
                    'verifiedSearchAliases': [person['name'], *person.get('aliases', [])],
                    'visualIdentityVerified': False,
                    'identityWarning': 'Curated source metadata is NOT photo identity, rights or game crop approval',
                },
            }
            if rights(candidate) == 'open_license_metadata':
                yield candidate


class Official:
    """Explicitly curated official/media source URLs; no implied reuse permission."""
    name = 'official'

    def __init__(self, records):
        self.records = records

    def search(self, person, http, round_number=0):
        for record in self.records:
            if record.get('personId') == person['plannedQuestionId']:
                yield {**record, 'provider': self.name, 'searchTime': now()}


class CommonsSearch:
    """Independent bulk Commons search: a Wikipedia timeout must not prevent it."""
    name = 'commons'

    def search(self, person, http, round_number=0):
        context = verified_identity(person, http)
        # Search the exact Chinese name before romanizations. Previously verified
        # English aliases were prepended, so rate limits / the per-person deadline
        # could be exhausted on homonyms before the native-name query ran.
        # Wikidata Q5 confirms the *alias mapping*, not a photo's subject.
        queries = [person['name'], person.get('reviewSearchQuery') or person.get('preferredImageQuery') or person['name']]
        if context:
            queries.extend(context['englishAliases'][:2])
        queries = list(dict.fromkeys(q for q in queries if str(q).strip()))
        seen=set()
        busy_fallbacks=0
        # Human-curated exact Commons file titles are discovery hints only.
        # Never infer identity, rights or visual approval from this field.
        # Exact imageinfo bypasses noisy CirrusSearch and is capped at 3 files.
        exact_files = []
        excluded = excluded_commons_keys(person)
        for raw in person.get('reviewExactCommonsFiles', [])[:3]:
            filename = str(raw).strip().removeprefix('File:')
            if (re.fullmatch(r'.{1,200}\.(?:jpg|jpeg|png|webp)', filename, re.I)
                    and not any(ch in filename for ch in ('/', chr(92), chr(10), chr(13)))
                    and source_key('https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(filename.replace(' ', '_'))) not in excluded):
                exact_files.append(filename)
        requests = ([('exact', person['name'])] if exact_files else [])
        requests.extend(('search', query) for query in dict.fromkeys(queries))
        for mode, query in requests:
            try:
                if mode == 'exact':
                    data = http.json('https://commons.wikimedia.org/w/api.php',
                        action='query', format='json', formatversion=2,
                        titles='|'.join('File:' + name for name in exact_files),
                        prop='imageinfo|categories', clcategories='Category:License review needed|Category:License review failed', cllimit=10, iiprop='url|extmetadata|size', iiurlwidth=1400)
                else:
                    data=http.json('https://commons.wikimedia.org/w/api.php',action='query',format='json',formatversion=2,
                        generator='search',gsrsearch=phrase_query(query),gsrnamespace=6,gsrlimit=12,gsroffset=(round_number%3)*12,
                        prop='imageinfo|categories', clcategories='Category:License review needed|Category:License review failed', cllimit=10,iiprop='url|extmetadata|size',iiurlwidth=1400)
            except SourceError as exc:
                # An unavailable exact-file lookup must not suppress normal search.
                if mode == 'exact':
                    continue
                if exc.code != 'source_api_busy':
                    raise
                # allimages uses title-prefix enumeration, not CirrusSearch.
                # Resolve a bounded set of exact files with normal imageinfo metadata.
                # A prefix match is never proof of the depicted person's identity.
                busy_fallbacks += 1
                listing = http.json('https://commons.wikimedia.org/w/api.php', action='query',
                    format='json', formatversion=2, list='allimages', aiprefix=str(query).strip(),
                    ailimit=8, aiprop='canonicaltitle')
                titles = [row.get('title') or ('File:' + row['name'])
                    for row in listing.get('query', {}).get('allimages', [])
                    if row.get('title') or row.get('name')]
                if not titles:
                    continue
                data = http.json('https://commons.wikimedia.org/w/api.php', action='query',
                    format='json', formatversion=2, titles='|'.join(titles),
                    prop='imageinfo|categories', clcategories='Category:License review needed|Category:License review failed', cllimit=10, iiprop='url|extmetadata|size', iiurlwidth=1400)
            pages = data.get('query', {}).get('pages', [])
            # A zero-result CirrusSearch is not proof that Commons has no
            # portrait. For an exact, reasonably distinctive Chinese name,
            # make ONE bounded filename-prefix lookup. Unlike an unquoted
            # full-text search, this cannot fan out into unrelated English
            # homonyms. The result is metadata only, never identity approval.
            if (mode == 'search' and not pages and query == person['name']
                    and re.fullmatch(r'[㐀-鿿]{3,8}', str(query).strip())):
                try:
                    listing = http.json('https://commons.wikimedia.org/w/api.php',
                        action='query', format='json', formatversion=2,
                        list='allimages', aiprefix=query, ailimit=8,
                        aiprop='canonicaltitle')
                    titles = [row.get('title') or ('File:' + row['name'])
                        for row in listing.get('query', {}).get('allimages', [])
                        if row.get('title') or row.get('name')]
                    if titles:
                        detail = http.json('https://commons.wikimedia.org/w/api.php',
                            action='query', format='json', formatversion=2,
                            titles='|'.join(titles), prop='imageinfo|categories',
                            clcategories='Category:License review needed|Category:License review failed',
                            cllimit=10, iiprop='url|extmetadata|size', iiurlwidth=1400)
                        pages = detail.get('query', {}).get('pages', [])
                except SourceError:
                    # A failing secondary lookup must not consume the rest of
                    # the person's ordinary search attempts.
                    pass
            for page in pages:
                for info in page.get('imageinfo',[]):
                    source=info.get('descriptionurl','')
                    if source_key(source) in excluded or source in seen:continue
                    seen.add(source)
                    ext=info.get('extmetadata',{});val=lambda key:clean(ext.get(key,{}).get('value',''))
                    license_url=val('LicenseUrl')
                    if license_url.startswith('http://creativecommons.org/'):license_url='https://'+license_url[7:]
                    evidence={'query':query,'identityWarning':'Caption/name match is preliminary evidence only'}
                    if mode == 'exact':
                        evidence['curatedExactFileHint'] = True
                        evidence['identityWarning'] = 'Curated exact-file lookup is not proof of the pictured person; independently verify caption and identity'
                    if context:
                        evidence.update(context['evidence'])
                        evidence['matchedAliases']=identity({**person,'aliases':context['aliases']},page.get('title','')+' '+val('ImageDescription'))
                    yield {'provider':self.name,'url':info.get('thumburl') or info.get('url',''),'originalUrl':info.get('url',''),
                        'downloadVariant':'wikimedia_thumbnail_1400' if info.get('thumburl') else 'original','source':source,
                        'filename':page.get('title','').removeprefix('File:'),'artist':val('Artist'),'credit':val('Credit'),
                        'license':val('LicenseShortName'),'licenseUrl':license_url,'caption':val('ImageDescription'), 'licenseReviewStatus':commons_review_status(page),
                        'identityEvidence':evidence,
                        'recognitionEvidence':{'requestedReplacement':person.get('reviewReason'),'representativeWorks':person.get('representativeWorks',[]),'note':'Familiar appearance must be reviewed'},
                        'searchTime':now(),'width':info.get('width'),'height':info.get('height')}
        if busy_fallbacks and not seen:
            raise SourceError('source_api_busy', 'CirrusSearch busy; exact file-prefix lookups found no candidates')


class EntityPortraits:
    """Authoritative bilingual name mapping, then independent portrait catalogues.

    A unique exact Chinese label/alias and Q5 statement is required. The entity
    mapping establishes search aliases, not visual identity or image rights.
    """
    name = 'entity'
    wikidata_api = 'https://www.wikidata.org/w/api.php'

    def __init__(self, allow_openverse=True):
        self.allow_openverse = allow_openverse

    def _resolve(self, person, http):
        cached = verified_identity(person, http)
        if cached:
            return cached['aliases'], cached['query'], cached['evidence'], cached['files']
        expected = {norm(value) for value in [person['name'], *person.get('acceptedAnswers', [])]
                    if len(norm(value)) >= 2}
        ids, articles, lookup_failures = [], {}, []
        # Exact title/pageprops is a direct lookup, independent of CirrusSearch.
        # Redirects are accepted only for requested names and the entity is still
        # required to have an exact Chinese label/alias and a Q5 human statement.
        titles = list(dict.fromkeys([person['name'], *person.get('acceptedAnswers', [])]))[:3]
        try:
            pages = http.json('https://zh.wikipedia.org/w/api.php', action='query', format='json', formatversion=2,
                              titles='|'.join(titles), redirects=1, converttitles=1,
                              prop='pageprops|info', ppprop='wikibase_item|disambiguation', inprop='url')
            query_data = pages.get('query', {})
            exact_titles = set(expected)
            for redirect in [*query_data.get('normalized', []), *query_data.get('converted', []), *query_data.get('redirects', [])]:
                if norm(redirect.get('from', '')) in exact_titles:
                    exact_titles.add(norm(redirect.get('to', '')))
            pages = query_data.get('pages', [])
            if isinstance(pages, dict):
                pages = pages.values()
            for page in pages:
                props = page.get('pageprops', {})
                qid = props.get('wikibase_item', '')
                title = page.get('title', '')
                title_name = re.split(r'[（(]', title, maxsplit=1)[0].strip()
                if ('missing' in page or 'disambiguation' in props or
                        not ({norm(title), norm(title_name)} & exact_titles) or
                        not re.fullmatch(r'Q[1-9][0-9]*', qid)):
                    continue
                ids.append(qid)
                articles[qid] = {'article': page.get('fullurl') or 'https://zh.wikipedia.org/wiki/' + urllib.parse.quote(title),
                                 'articleTitle': title, 'articleLookup': 'exact title with redirects; not a search result'}
        except SourceError as exc:
            lookup_failures.append({'provider': 'wikipedia_exact', 'code': exc.code, 'message': str(exc)[:300]})
        # An exact Wikipedia title may belong to a namesake (e.g. the
        # historical 苗可秀 rather than actress Nora Miao). A curator-pinned
        # QID is a stronger entity selector, but it must STILL pass the
        # exact Chinese-name and P31=Q5 checks below. Never attach the
        # namesake's Wikipedia article as evidence for the pinned person.
        pinned_qid = person.get('wikidataId')
        if pinned_qid:
            if not re.fullmatch(r'Q[1-9][0-9]*', str(pinned_qid)):
                raise SourceError('identity_entity_mismatch', 'Invalid pinned Wikidata QID')
            if ids and pinned_qid not in ids:
                lookup_failures.append({
                    'provider': 'wikipedia_exact', 'code': 'homonym_page_ignored',
                    'message': 'Exact-title Wikipedia entity differs from curated QID; use pinned QID with independent Q5/name validation'})
            ids = [pinned_qid]
        if not ids:
            result = http.json(self.wikidata_api, action='wbsearchentities', format='json',
                               search=person['name'], language='zh', uselang='zh', type='item', limit=5)
            ids = [row.get('id') for row in result.get('search', [])
                   if re.fullmatch(r'Q[1-9][0-9]*', str(row.get('id', '')))]
        ids = list(dict.fromkeys(ids))
        if not ids:
            raise SourceError('identity_not_found', 'No Wikidata entity candidates for the exact person name')
        data = http.json(self.wikidata_api, action='wbgetentities', format='json',
                         ids='|'.join(ids), props='labels|aliases|claims|sitelinks',
                         languages='en|zh|zh-hant|zh-hans|zh-tw|zh-cn', sitefilter='zhwiki|enwiki|commonswiki')
        eligible = []
        for qid in ids:
            entity = data.get('entities', {}).get(qid, {})
            chinese = [row.get('value', '') for lang, row in entity.get('labels', {}).items() if lang.startswith('zh')]
            chinese.extend(row.get('value', '') for lang, rows in entity.get('aliases', {}).items()
                           if lang.startswith('zh') for row in rows)
            # Some Taiwanese performers have only an English Wikidata label,
            # but a correctly typed Chinese native name (P1559). Without
            # this, an exact Q5 person with a valid P18 is discarded as
            # identity_unconfirmed before its photo can even be reviewed.
            # Accept only non-deprecated, Chinese-language monolingual text
            # matching the requested full name; never infer identity from
            # a substring, search snippet, or an English P1559 value.
            chinese.extend(
                value['text']
                for claim in entity.get('claims', {}).get('P1559', [])
                if claim.get('rank') != 'deprecated'
                for value in [claim.get('mainsnak', {}).get('datavalue', {}).get('value')]
                if isinstance(value, dict)
                and str(value.get('language', '')).lower().startswith('zh')
                and isinstance(value.get('text'), str)
            )
            matched = [value for value in chinese if norm(value) in expected]
            human = any(claim.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id') == 'Q5'
                        for claim in entity.get('claims', {}).get('P31', []) if claim.get('rank') != 'deprecated')
            if matched and human:
                eligible.append((qid, entity, matched))
        if len(eligible) != 1:
            code = 'identity_ambiguous' if len(eligible) > 1 else 'identity_unconfirmed'
            raise SourceError(code, 'Expected exactly one exact-name Q5 human; found ' + str(len(eligible)))
        qid, entity, matched = eligible[0]
        # A matching name and P31=Q5 are insufficient for known homonyms.
        # A human-curated QID in the existing roster must match the resolved
        # entity before its P18, English aliases or photo searches are used.
        pinned_qid = person.get('wikidataId')
        if pinned_qid and qid != pinned_qid:
            raise SourceError('identity_entity_mismatch',
                              'Resolved ' + qid + ' differs from pinned ' + pinned_qid +
                              ' for ' + person['name'])
        english = [entity.get('labels', {}).get('en', {}).get('value', '')]
        english.extend(row.get('value', '') for row in entity.get('aliases', {}).get('en', []))
        # Short English fragments can match unrelated filenames. Keep complete names.
        blocked_english = {norm(value) for value in person.get('photoSearchBlockedEnglishAliases', [])}
        english = [value for value in dict.fromkeys(english) if re.search('[A-Za-z]', value)
                   and len(norm(value)) >= 5 and norm(value) not in blocked_english][:4]
        aliases = list(dict.fromkeys([person['name'], *matched, *english]))
        # P373 is scoped to the already verified exact-name Q5 entity.
        # It is a discovery hint, never proof that a category photo depicts it.
        commons_categories = [
            claim.get('mainsnak', {}).get('datavalue', {}).get('value')
            for claim in entity.get('claims', {}).get('P373', [])
            if claim.get('rank') != 'deprecated'
        ]
        commons_category = next((
            value.strip().removeprefix('Category:')
            for value in commons_categories
            if isinstance(value, str) and re.fullmatch(r'[^|#\r\n]{2,120}', value.strip())
        ), '')
        category_evidence = 'Wikidata P373 on exact-name Q5 entity' if commons_category else None
        # Many verified Q5 performers have a Commons category sitelink but no
        # P373 statement. The sitelink belongs to this *same* resolved QID;
        # never guess a category from a search result or an unverified alias.
        if not commons_category:
            sitelink = entity.get('sitelinks', {}).get('commonswiki', {}).get('title')
            if (isinstance(sitelink, str) and
                    re.fullmatch(r'Category:[^|#\r\n]{2,120}', sitelink)):
                commons_category = sitelink[len('Category:'):].strip()
                category_evidence = 'Wikidata commonswiki sitelink on exact-name Q5 entity'
        evidence = {'wikidataId': qid, 'mappingSource': 'https://www.wikidata.org/wiki/' + qid,
                    'exactChineseAliases': matched, 'verifiedSearchAliases': aliases,
                    'commonsCategory': commons_category,
                    'commonsCategoryEvidence': category_evidence,
                    'entityTypeEvidence': 'P31=Q5', 'retrievedAt': now(),
                    'visualIdentityVerified': False,
                    'identityWarning': 'Entity names only establish search aliases. Verify the pictured person and caption.'}
        evidence.update(articles.get(qid, {}))
        if lookup_failures:
            evidence['lookupWarnings'] = lookup_failures
        files = [claim.get('mainsnak', {}).get('datavalue', {}).get('value')
                 for claim in entity.get('claims', {}).get('P18', []) if claim.get('rank') != 'deprecated']
        files = [value for value in files if isinstance(value, str)][:3]
        if not hasattr(http, 'verified_identities'):
            http.verified_identities = {}
        # Keep verified English names as fallbacks, but prefer the native
        # name to avoid spending the source budget on romanized homonyms.
        query = person['name']
        http.verified_identities[identity_key(person)] = {'aliases': aliases, 'englishAliases': english,
                                                        'query': query, 'evidence': evidence, 'files': files}
        return aliases, query, evidence, files

    def search(self, person, http, round_number=0):
        aliases, query, mapping, entity_files = self._resolve(person, http)
        excluded = excluded_commons_keys(person)
        entity_files = [filename for filename in entity_files
                        if source_key('https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(filename.replace(' ', '_'))) not in excluded]
        enriched = {**person, 'aliases': aliases}
        failures, seen, commons, yielded = [], set(), [], False
        # Exact Wikidata P18 first, then native-name Commons search, then
        # up to two independently verified English names. Never promote a
        # search hit to visual identity evidence without a matching caption.
        requests = []
        if entity_files:
            requests.append((query, {'titles': '|'.join('File:' + value for value in entity_files)}))
        # Bounded P373 category lookup can discover portraits whose filenames
        # omit the native/English name. Category membership is NOT approval:
        # the normal caption/P18, rights, crop and human-review gates remain.
        category = mapping.get('commonsCategory')
        if category:
            try:
                listing = http.json('https://commons.wikimedia.org/w/api.php',
                    action='query', format='json', formatversion=2,
                    list='categorymembers', cmtitle='Category:' + category,
                    cmtype='file', cmlimit=12)
                titles = [item['title'] for item in listing.get('query', {}).get('categorymembers', [])
                          if re.fullmatch(r'File:[^|\r\n]{1,200}\.(?:jpg|jpeg|png|webp)',
                                          str(item.get('title', '')), re.I)]
                if titles:
                    requests.append(('commons_category_p373', {'titles': '|'.join(titles)}))
            except SourceError as exc:
                failures.append({'provider': 'commons_category_p373', 'code': exc.code,
                                 'message': str(exc)[:300]})
        english_fallbacks = [alias for alias in aliases if re.search(r'[A-Za-z]', alias)][:2]
        for search_term in dict.fromkeys([query, *english_fallbacks]):
            requests.append((search_term, {'generator': 'search',
                'gsrsearch': phrase_query(search_term), 'gsrnamespace': 6,
                'gsrlimit': 12, 'gsroffset': (round_number % 3) * 12}))
        for source_query, request in requests:
            try:
                data = http.json('https://commons.wikimedia.org/w/api.php', action='query', format='json', formatversion=2,
                                 prop='imageinfo|categories', clcategories='Category:License review needed|Category:License review failed', cllimit=10, iiprop='url|extmetadata|size', iiurlwidth=1400, **request)
                pages = list(data.get('query', {}).get('pages', []))
                pages.sort(key=lambda row: (not any(word in row.get('title', '').lower() for word in ('portrait', 'cropped')), row.get('title', '')))
                for page in pages:
                    filename = page.get('title', '').removeprefix('File:')
                    if not re.search(r'\.(jpg|jpeg|png|webp)$', filename, re.I):
                        continue
                    for info in page.get('imageinfo', []):
                        source = info.get('descriptionurl', '')
                        if not source or source_key(source) in seen or source_key(source) in excluded:
                            continue
                        seen.add(source_key(source))
                        ext = info.get('extmetadata', {})
                        val = lambda key: clean(ext.get(key, {}).get('value', ''))
                        license_url = val('LicenseUrl')
                        if license_url.startswith('http://creativecommons.org/'):
                            license_url = 'https://' + license_url[7:]
                        caption = val('ImageDescription')
                        evidence = {**mapping, 'query': source_query,
                                    'matchedAliases': identity(enriched, filename + ' ' + caption),
                                    'discoveryWarnings': list(failures)}
                        if filename in entity_files:
                            evidence['claim'] = 'P18'
                        commons.append({'provider': 'commons', 'url': info.get('thumburl') or info.get('url', ''),
                               'originalUrl': info.get('url', ''), 'source': source, 'filename': filename,
                               'downloadVariant': 'wikimedia_thumbnail_1400' if info.get('thumburl') else 'original',
                               'artist': val('Artist'), 'credit': val('Credit'), 'license': val('LicenseShortName'),
                               'licenseUrl': license_url, 'caption': caption, 'licenseReviewStatus': commons_review_status(page), 'identityEvidence': evidence,
                               'recognitionEvidence': {'representativeWorks': person.get('representativeWorks', []),
                                   'requestedReplacement': person.get('reviewReason'), 'note': 'Familiar appearance has not been visually reviewed'},
                               'searchTime': now(), 'width': info.get('width'), 'height': info.get('height')})
            except SourceError as exc:
                failures.append({'provider': 'commons', 'code': exc.code, 'message': str(exc)[:300]})
        # The consumer has a small candidate quota. Unrelated catalogue hits must
        # not consume it before a name-bearing/licensed portrait is considered.
        def order(candidate):
            evidence = candidate['identityEvidence']
            supported = bool(evidence.get('matchedAliases') or evidence.get('claim') == 'P18')
            return (not supported, rights(candidate) != 'open_license_metadata',
                    not any(word in candidate['filename'].casefold() for word in ('portrait', 'cropped')))
        commons.sort(key=order)
        supported = [candidate for candidate in commons if not order(candidate)[0]]
        for candidate in supported[:3]:
            yielded = True
            yield candidate
        # The standalone pipeline explicitly selects providers. Its entity
        # adapter must not silently call Openverse during Commons-only runs.
        # Keep the legacy fallback opt-in for other callers and fixtures.
        if self.allow_openverse:
            # A refused Commons host must not prevent an independent catalogue search.
            # Limit the first Commons tranche to three, so even a four-item consumer
            # quota reaches the independent source. The separate Openverse provider
            # also retains the verified aliases if this generator is closed early.
            try:
                for candidate in Openverse().search(person, http, round_number):
                    if not candidate.get('source') or source_key(candidate['source']) in seen:
                        continue
                    seen.add(source_key(candidate['source']))
                    candidate['identityEvidence'] = {**candidate['identityEvidence'],
                        'matchedAliases': identity(enriched, candidate.get('filename', '') + ' ' + candidate.get('caption', '')),
                        'discoveryWarnings': list(failures)}
                    candidate['recognitionEvidence'] = {'representativeWorks': person.get('representativeWorks', []),
                        'requestedReplacement': person.get('reviewReason'), 'note': 'Familiar appearance has not been visually reviewed'}
                    yielded = True
                    yield candidate
            except SourceError as exc:
                failures.append({'provider': 'openverse', 'code': exc.code, 'message': str(exc)[:300]})
        first = {source_key(candidate['source']) for candidate in supported[:3]}
        for candidate in commons:
            if source_key(candidate['source']) in first:
                continue
            yielded = True
            yield candidate
        if not yielded and failures:
            last = failures[-1]
            raise SourceError(last['code'], 'No catalogue response: ' + last['message'])
