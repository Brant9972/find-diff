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
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HTTP:
    def __init__(self, attempts=3, interval=.8, budget=None):
        self.attempts, self.interval, self.budget = attempts, interval, budget
        self.last = {}

    def get(self, url, params=None):
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        host = public_https(url)
        for attempt in range(self.attempts):
            if self.budget and time.monotonic() >= self.budget:
                raise SourceError('time_budget', 'Batch time budget reached')
            time.sleep(max(0, self.interval - (time.monotonic() - self.last.get(host, 0))))
            try:
                with urllib.request.build_opener(HTTPSRedirect()).open(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=20) as response:
                    if int(response.headers.get('Content-Length', '0')) > MAX_BYTES:
                        raise SourceError('oversize', 'Response exceeds 14 MB')
                    data = response.read(MAX_BYTES + 1)
                    if len(data) > MAX_BYTES:
                        raise SourceError('oversize', 'Response exceeds 14 MB')
                    return data
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt + 1 == self.attempts:
                    raise SourceError('http_' + str(exc.code), str(exc)) from exc
                retry = exc.headers.get('Retry-After', '2')
                try:
                    delay = float(retry)
                except ValueError:
                    try:
                        delay = (parsedate_to_datetime(retry) - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                    except (ValueError, TypeError):
                        delay = 2
                time.sleep(max(0, min(delay, 10)))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if 'Tunnel connection failed: 403' in str(exc):
                    raise SourceError('proxy_access_denied', str(exc)) from exc
                if attempt + 1 == self.attempts:
                    raise SourceError('network_error', str(exc)) from exc
                time.sleep(2 ** attempt)
            finally:
                self.last[host] = time.monotonic()
        raise SourceError('network_error', 'Request attempts exhausted')

    def json(self, url, **params):
        try:
            return json.loads(self.get(url, params or None))
        except (ValueError, UnicodeError) as exc:
            raise SourceError('invalid_metadata', 'Source returned invalid JSON') from exc


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
                    yield {'provider': self.name, 'url': info.get('url', ''), 'source': info.get('descriptionurl', ''),
                           'filename': filename, 'artist': val('Artist'), 'credit': val('Credit'),
                           'license': val('LicenseShortName'), 'licenseUrl': val('LicenseUrl'),
                           'caption': val('ImageDescription'), 'identityEvidence': evidence,
                           'recognitionEvidence': {'representativeWorks': person.get('representativeWorks', []), 'matchedWorks': [w for w in person.get('representativeWorks', []) if isinstance(w, str) and norm(w) in norm(filename + ' ' + val('ImageDescription'))], 'note': 'Search context only; recognizability not verified'},
                           'searchTime': now(), 'width': info.get('width'), 'height': info.get('height')}


class Openverse:
    name = 'openverse'

    def search(self, person, http, round_number=0):
        aliases = [person['name'], *person.get('aliases', [])]
        query = aliases[round_number % len(aliases)]
        data = http.json('https://api.openverse.org/v1/images/', q=query, page_size=20, page=1 + round_number % 3, license_type='commercial,modification')
        for row in data.get('results', []):
            code, version = row.get('license', ''), row.get('license_version', '')
            yield {'provider': self.name, 'url': row.get('url', ''), 'source': row.get('foreign_landing_url', ''),
                   'filename': urllib.parse.unquote(urllib.parse.urlsplit(row.get('url', '')).path.rsplit('/', 1)[-1]),
                   'artist': row.get('creator', ''), 'license': 'CC ' + code.upper() + ' ' + version if code != 'cc0' else 'CC0',
                   'licenseUrl': row.get('license_url', ''), 'caption': row.get('title', ''),
                   'identityEvidence': {'query': query, 'identityWarning': 'Search match only; verify original page and pictured person'},
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
