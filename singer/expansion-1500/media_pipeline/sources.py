"""Bounded, auditable source adapters. Public availability is not a licence."""
import datetime
import html
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
    p = urllib.parse.urlsplit(str(url or ''))
    path = urllib.parse.unquote(p.path).replace('_', ' ').casefold().rstrip('/')
    # Wikimedia descriptions can appear under either language domain.
    if '/wiki/file:' in path:
        return 'wikimedia:' + path.split('/wiki/file:', 1)[1]
    return (p.hostname or '').casefold() + path + ('?' + p.query if p.query else '')


def clean(value):
    return html.unescape(re.sub('<[^>]+>', '', str(value or ''))).strip()


def identity(person, text):
    aliases = [person['name'], *person.get('aliases', []), *person.get('acceptedAnswers', [])]
    return [x for x in aliases if len(norm(x)) >= 2 and norm(x) in norm(text)]


def identity_key(person):
    return tuple(sorted({norm(value) for value in [person['name'], *person.get('acceptedAnswers', [])]}))


def verified_identity(person, http):
    """Per-person HTTP context; only the Q5/exact-name resolver may populate it."""
    return getattr(http, 'verified_identities', {}).get(identity_key(person))


def phrase_query(value):
    # Commons search otherwise treats a romanized name as independent tokens.
    return '"' + str(value).replace('"', ' ').strip() + '" filetype:bitmap'


def rights(candidate):
    """Conservative machine eligibility, never a final legal or human approval."""
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
        # May be shared by concurrent workers. Each worker still owns its time budget.
        self.blocked_hosts = blocked_hosts if blocked_hosts is not None else {}
        self.verified_identities = {}
        self.openverse_results = {}

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

    def get(self, url, params=None):
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        host = public_https(url)
        self._refusal(host)
        # Retries share one wall budget; slow downloads cannot multiply socket timeout by attempts.
        deadline = time.monotonic() + self.timeout
        if self.budget is not None:
            deadline = min(deadline, self.budget)
        self._seconds_left(deadline)
        for attempt in range(self.attempts):
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
                             titles='File:' + filename, prop='imageinfo', iiprop='url|extmetadata|size', iiurlwidth=1400)
            for page in data.get('query', {}).get('pages', []):
                for info in page.get('imageinfo', []):
                    ext = info.get('extmetadata', {})
                    val = lambda key: clean(ext.get(key, {}).get('value', ''))
                    yield {'provider': self.name, 'url': info.get('thumburl') or info.get('url', ''), 'originalUrl': info.get('url', ''),
                           'downloadVariant': 'wikimedia_thumbnail_1400' if info.get('thumburl') else 'original', 'source': info.get('descriptionurl', ''),
                           'filename': filename, 'artist': val('Artist'), 'credit': val('Credit'),
                           'license': val('LicenseShortName'), 'licenseUrl': val('LicenseUrl'),
                           'caption': val('ImageDescription'), 'identityEvidence': evidence,
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
        queries = [person['name'], person.get('reviewSearchQuery') or person.get('preferredImageQuery') or person['name']]
        if context:
            queries = [*context['englishAliases'][:2], *queries]
        seen=set()
        for query in dict.fromkeys(queries):
            data=http.json('https://commons.wikimedia.org/w/api.php',action='query',format='json',formatversion=2,
                generator='search',gsrsearch=phrase_query(query),gsrnamespace=6,gsrlimit=12,gsroffset=(round_number%3)*12,
                prop='imageinfo',iiprop='url|extmetadata|size',iiurlwidth=1400)
            for page in data.get('query',{}).get('pages',[]):
                for info in page.get('imageinfo',[]):
                    source=info.get('descriptionurl','')
                    if source in seen:continue
                    seen.add(source)
                    ext=info.get('extmetadata',{});val=lambda key:clean(ext.get(key,{}).get('value',''))
                    license_url=val('LicenseUrl')
                    if license_url.startswith('http://creativecommons.org/'):license_url='https://'+license_url[7:]
                    evidence={'query':query,'identityWarning':'Caption/name match is preliminary evidence only'}
                    if context:
                        evidence.update(context['evidence'])
                        evidence['matchedAliases']=identity({**person,'aliases':context['aliases']},page.get('title','')+' '+val('ImageDescription'))
                    yield {'provider':self.name,'url':info.get('thumburl') or info.get('url',''),'originalUrl':info.get('url',''),
                        'downloadVariant':'wikimedia_thumbnail_1400' if info.get('thumburl') else 'original','source':source,
                        'filename':page.get('title','').removeprefix('File:'),'artist':val('Artist'),'credit':val('Credit'),
                        'license':val('LicenseShortName'),'licenseUrl':license_url,'caption':val('ImageDescription'),
                        'identityEvidence':evidence,
                        'recognitionEvidence':{'requestedReplacement':person.get('reviewReason'),'representativeWorks':person.get('representativeWorks',[]),'note':'Familiar appearance must be reviewed'},
                        'searchTime':now(),'width':info.get('width'),'height':info.get('height')}


class EntityPortraits:
    """Authoritative bilingual name mapping, then independent portrait catalogues.

    A unique exact Chinese label/alias and Q5 statement is required. The entity
    mapping establishes search aliases, not visual identity or image rights.
    """
    name = 'entity'
    wikidata_api = 'https://www.wikidata.org/w/api.php'

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
                         languages='en|zh|zh-hant|zh-hans|zh-tw|zh-cn', sitefilter='zhwiki|enwiki')
        eligible = []
        for qid in ids:
            entity = data.get('entities', {}).get(qid, {})
            chinese = [row.get('value', '') for lang, row in entity.get('labels', {}).items() if lang.startswith('zh')]
            chinese.extend(row.get('value', '') for lang, rows in entity.get('aliases', {}).items()
                           if lang.startswith('zh') for row in rows)
            matched = [value for value in chinese if norm(value) in expected]
            human = any(claim.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id') == 'Q5'
                        for claim in entity.get('claims', {}).get('P31', []) if claim.get('rank') != 'deprecated')
            if matched and human:
                eligible.append((qid, entity, matched))
        if len(eligible) != 1:
            code = 'identity_ambiguous' if len(eligible) > 1 else 'identity_unconfirmed'
            raise SourceError(code, 'Expected exactly one exact-name Q5 human; found ' + str(len(eligible)))
        qid, entity, matched = eligible[0]
        english = [entity.get('labels', {}).get('en', {}).get('value', '')]
        english.extend(row.get('value', '') for row in entity.get('aliases', {}).get('en', []))
        # Short English fragments can match unrelated filenames. Keep complete names.
        blocked_english = {norm(value) for value in person.get('photoSearchBlockedEnglishAliases', [])}
        english = [value for value in dict.fromkeys(english) if re.search('[A-Za-z]', value)
                   and len(norm(value)) >= 5 and norm(value) not in blocked_english][:4]
        aliases = list(dict.fromkeys([person['name'], *matched, *english]))
        evidence = {'wikidataId': qid, 'mappingSource': 'https://www.wikidata.org/wiki/' + qid,
                    'exactChineseAliases': matched, 'verifiedSearchAliases': aliases,
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
        query = english[0] if english else person['name']
        http.verified_identities[identity_key(person)] = {'aliases': aliases, 'englishAliases': english,
                                                        'query': query, 'evidence': evidence, 'files': files}
        return aliases, query, evidence, files

    def search(self, person, http, round_number=0):
        aliases, query, mapping, entity_files = self._resolve(person, http)
        enriched = {**person, 'aliases': aliases}
        failures, seen, commons, yielded = [], set(), [], False
        requests = []
        if entity_files:
            requests.append({'titles': '|'.join('File:' + value for value in entity_files)})
        requests.append({'generator': 'search', 'gsrsearch': phrase_query(query),
                         'gsrnamespace': 6, 'gsrlimit': 15, 'gsroffset': (round_number % 3) * 15})
        for request in requests:
            try:
                data = http.json('https://commons.wikimedia.org/w/api.php', action='query', format='json', formatversion=2,
                                 prop='imageinfo', iiprop='url|extmetadata|size', iiurlwidth=1400, **request)
                pages = list(data.get('query', {}).get('pages', []))
                pages.sort(key=lambda row: (not any(word in row.get('title', '').lower() for word in ('portrait', 'cropped')), row.get('title', '')))
                for page in pages:
                    filename = page.get('title', '').removeprefix('File:')
                    if not re.search(r'\.(jpg|jpeg|png|webp)$', filename, re.I):
                        continue
                    for info in page.get('imageinfo', []):
                        source = info.get('descriptionurl', '')
                        if not source or source_key(source) in seen:
                            continue
                        seen.add(source_key(source))
                        ext = info.get('extmetadata', {})
                        val = lambda key: clean(ext.get(key, {}).get('value', ''))
                        license_url = val('LicenseUrl')
                        if license_url.startswith('http://creativecommons.org/'):
                            license_url = 'https://' + license_url[7:]
                        caption = val('ImageDescription')
                        evidence = {**mapping, 'query': query,
                                    'matchedAliases': identity(enriched, filename + ' ' + caption),
                                    'discoveryWarnings': list(failures)}
                        if filename in entity_files:
                            evidence['claim'] = 'P18'
                        commons.append({'provider': 'commons', 'url': info.get('thumburl') or info.get('url', ''),
                               'originalUrl': info.get('url', ''), 'source': source, 'filename': filename,
                               'downloadVariant': 'wikimedia_thumbnail_1400' if info.get('thumburl') else 'original',
                               'artist': val('Artist'), 'credit': val('Credit'), 'license': val('LicenseShortName'),
                               'licenseUrl': license_url, 'caption': caption, 'identityEvidence': evidence,
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
