import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.delivery import build_assets, publish_links

REVEAL = {key: [.08, .2, .92, bottom] for key, bottom in
          [('eyes', .4), ('nose', .55), ('mouth', .7), ('chin', .9)]}
REVEAL['full'] = [0, 0, 1, 1]


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.root = self.repo / 'singer'
        self.directory = self.root / 'expansion-1500/pipeline'
        self.root.mkdir()
        self.state = {'schemaVersion': 2, 'chatgptReview': {'sha256': 'review-digest'}, 'people': {}}
        self._person('t1', '測試人物', 'pending_evidence')
        self._person('t2', '裁切人物', 'pending_review')
        self._person('t3', '退件人物', 'rejected')
        self._person('t4', '舊版人物', 'superseded')

    def tearDown(self):
        self.temp.cleanup()

    def _person(self, person_id, name, status):
        game = self.root / 'expansion-1500/review_photos' / (person_id + '.png')
        game.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new('RGB', (600, 720), '#a84c32')
        image.putpixel((300, 200), (10, 200, 90))
        image.save(game)
        source = game.with_suffix('.bin')
        Image.new('RGB', (900, 1200), '#339955').save(source, 'JPEG')
        candidate = {'id': 'candidate-' + person_id, 'status': status, 'gamePath': str(game.relative_to(self.root)),
                     'gameSha256': hashlib.sha256(game.read_bytes()).hexdigest(), 'reveal': copy.deepcopy(REVEAL),
                     'originalPath': str(source.relative_to(self.root)), 'originalSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                     'source': 'https://commons.wikimedia.org/wiki/File:Example.jpg', 'artist': 'Photographer',
                     'license': 'CC BY 4.0', 'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                     'caption': name + '</script><img src=x onerror=alert(1)>', 'eligibleForLive': False}
        self.state['people'][person_id] = {'personId': person_id, 'name': name,
                                         'status': 'pending_review', 'candidates': [candidate]}
        return candidate

    def _git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def _commit(self):
        self._git('init')
        self._git('add', 'singer')
        self._git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.org', 'commit', '-m', 'Review pixels fixture')
        return self._git('rev-parse', 'HEAD')

    def test_assets_have_real_pixels_proper_extensions_and_exclude_rejected(self):
        before = copy.deepcopy(self.state)
        result = build_assets(self.root, self.directory, self.state, 'fixture-run')
        self.assertEqual(result['peopleCount'], 2)
        self.assertEqual(result['photoCount'], 2)
        self.assertEqual({p['personId'] for p in result['photos']}, {'t1', 't2'})
        self.assertEqual(self.state, before)
        photo = result['photos'][0]
        self.assertTrue(photo['sourceImage']['path'].endswith('.jpg'))
        self.assertEqual(photo['sourceImage']['mimeType'], 'image/jpeg')
        source = self.root / self.state['people']['t1']['candidates'][0]['originalPath']
        self.assertEqual(source.read_bytes(), (self.root / photo['sourceImage']['path']).read_bytes())
        self.assertEqual(photo['candidateImage']['sha256'], photo['gameSha256'])
        with Image.open(self.root / photo['stageImages']['eyes']['path']) as image:
            self.assertEqual(image.size, (600, 720))
            self.assertEqual(image.getpixel((0, 0)), (23, 21, 31))
            self.assertEqual(image.getpixel((300, 200)), (10, 200, 90))
        with Image.open(self.root / photo['stageImages']['full']['path']) as image:
            self.assertEqual(image.getpixel((0, 0)), (168, 76, 50))
        self.assertEqual(len(photo['stageImages']), 5)
        self.assertTrue(result['contactSheets'])
        self.assertTrue(result['revealSheets'])

    def test_build_is_repeatable_for_the_same_package(self):
        first = build_assets(self.root, self.directory, self.state, 'fixture-run')
        second = build_assets(self.root, self.directory, self.state, 'fixture-run')
        self.assertEqual(first, second)
        raw = (self.root / first['assetManifestPath']).read_bytes()
        self.assertEqual(json.loads(raw), first)

    def test_changed_candidate_hash_is_not_exported(self):
        self.state['people']['t1']['candidates'][0]['gameSha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            build_assets(self.root, self.directory, self.state, 'bad-hash')

    def test_invalid_reveal_and_paths_are_not_exported(self):
        self.state['people']['t1']['candidates'][0]['reveal']['nose'][3] = .1
        with self.assertRaisesRegex(ValueError, 'Invalid reveal'):
            build_assets(self.root, self.directory, self.state, 'invalid-reveal')
        with self.assertRaisesRegex(ValueError, 'run ID'):
            build_assets(self.root, self.directory, self.state, '../../escape')

    def test_publish_links_are_absolute_commit_pinned_and_pixels_are_committed(self):
        manifest = build_assets(self.root, self.directory, self.state, 'fixture-run')
        sha = self._commit()
        result = publish_links(self.root, self.directory, manifest, sha, repository='owner/project')
        self.assertEqual(result['assetCommit'], sha)
        photo = result['photos'][0]
        self.assertEqual(photo['candidateImage']['rawUrl'],
                         f'https://raw.githubusercontent.com/owner/project/{sha}/singer/' + photo['candidateImage']['path'])
        self.assertIn('/blob/' + sha + '/', photo['candidateImage']['githubViewUrl'])
        self.assertTrue(photo['candidateImage']['githubRawUrl'].endswith('?raw=true'))
        self.assertTrue(all(x['rawUrl'].startswith('https://') for x in photo['stageImages'].values()))
        markdown = (self.directory / 'review-public/latest.md').read_text()
        self.assertIn('![', markdown)
        self.assertIn('https://raw.githubusercontent.com/owner/project/' + sha, markdown)
        self.assertNotIn('file://', markdown)
        self.assertNotIn('</script><img', markdown)
        self.assertIn('來源頁', markdown)
        self.assertIn('授權紀錄', markdown)
        self.assertIn('五階段總覽', markdown)
        self.assertFalse(photo['eligibleForLive'])
        self.assertFalse(photo['metadata']['humanIdentityVerifiedByExporter'])

    def test_uncommitted_asset_manifest_cannot_publish_dead_urls(self):
        # Commit the original source files, then create the package: that SHA lacks its pixels.
        sha = self._commit()
        manifest = build_assets(self.root, self.directory, self.state, 'new-package')
        with self.assertRaises(subprocess.CalledProcessError):
            publish_links(self.root, self.directory, manifest, sha)
        self.assertFalse((self.directory / 'review-public/latest.json').exists())
        with self.assertRaisesRegex(ValueError, 'full immutable'):
            publish_links(self.root, self.directory, manifest, 'main')

    def test_original_source_may_be_missing_but_not_silently_faked(self):
        self.state['people']['t1']['candidates'][0].pop('originalPath')
        manifest = build_assets(self.root, self.directory, self.state, 'no-source')
        self.assertIsNone(manifest['photos'][0]['sourceImage'])
        sha = self._commit()
        publish_links(self.root, self.directory, manifest, sha)
        self.assertIn('來源圖片尚未保存', (self.directory / 'review-public/latest.md').read_text())

    def test_unsafe_external_links_are_not_rendered_as_links(self):
        candidate = self.state['people']['t1']['candidates'][0]
        candidate['source'] = 'javascript:alert(1)'
        candidate['licenseUrl'] = 'https://user:password@example.org/license'
        manifest = build_assets(self.root, self.directory, self.state, 'unsafe-source')
        self.assertIsNone(manifest['photos'][0]['metadata']['sourcePage'])
        self.assertIsNone(manifest['photos'][0]['metadata']['licenseUrl'])

    def test_markdown_exposes_existing_evidence_without_claiming_human_verification(self):
        candidate = self.state['people']['t1']['candidates'][0]
        candidate.update({
            'credit': 'Provided by original photographer',
            'externalSourceLinks': ['https://www.flickr.com/photos/example/123/', 'javascript:alert(1)'],
            'identityEvidence': {
                'article': 'https://zh.wikipedia.org/wiki/Example',
                'mappingSource': 'https://www.wikidata.org/wiki/Q123', 'wikidataId': 'Q123',
                'verifiedSearchAliases': ['測試人物', 'Example Person'],
                'captionAliasMatches': ['測試人物'], 'entityTypeEvidence': 'P31=Q5',
                'identityWarning': 'Only a name match <not approved>',
                'biography': {'article': 'https://zh.wikipedia.org/wiki/Example', 'excerpt': 'Example biography'},
                'externalSourceLinks': ['https://www.flickr.com/photos/example/123/'],
            },
            'recognitionEvidence': {'representativeWorks': ['Example Work'], 'note': 'Search context only'},
            'parentCandidateId': 'older-crop',
            'sourceAlignmentEvidence': {'method': 'ORB + RANSAC', 'matches': 49, 'inliers': 34,
                                        'inlierRatio': 34 / 49, 'sourceImageSize': [900, 1200],
                                        'sourceSha256': 'a' * 64, 'cropBoxInParent': [10, 20, 300, 400],
                                        'note': 'Same-photo pixels only'},
        })
        before = copy.deepcopy(self.state)
        manifest = build_assets(self.root, self.directory, self.state, 'visible-evidence')
        sha = self._commit()
        result = publish_links(self.root, self.directory, manifest, sha)
        markdown = (self.directory / 'review-public/latest.md').read_text()
        for expected in ['https://zh.wikipedia.org/wiki/Example', 'https://www.wikidata.org/wiki/Q123',
                         'Example Person', 'Example biography', '圖說名稱相符紀錄：測試人物',
                         'Provided by original photographer', 'https://www.flickr.com/photos/example/123/',
                         '辨識度：尚未經 ChatGPT 目視驗證', 'Example Work', 'ORB + RANSAC',
                         '特徵配對數：49', '一致配對數：34', '對應來源 SHA-256：' + 'a' * 64,
                         '母候選 ID：older-crop', '不能確認人物、權利或裁切適用性',
                         '來源像素對應：尚無自動對應證據',
                         'singer/expansion-1500/pipeline/chatgpt-review/latest.json',
                         'automation/celebrity-photo-pipeline']:
            self.assertIn(expected, markdown)
        self.assertEqual(markdown.count('[外部原始來源](<https://www.flickr.com/photos/example/123/>)'), 1)
        self.assertNotIn('javascript:alert', markdown)
        self.assertNotIn('<not approved>', markdown)
        self.assertEqual(self.state, before)
        self.assertFalse(result['photos'][0]['metadata']['humanIdentityVerifiedByExporter'])
        self.assertFalse(result['photos'][0]['metadata']['humanRightsVerifiedByExporter'])


    def test_source_only_images_get_real_preview_links_without_approval(self):
        candidate = self._person('t5', '待裁切人物', 'manual_crop_required')
        candidate.pop('gamePath')
        candidate.pop('gameSha256')
        candidate.pop('reveal')
        candidate['cropFailure'] = 'Face is too small'
        self.state['people']['t5']['status'] = 'download_failed'
        self.state['people']['t3']['status'] = 'published'
        manifest = build_assets(self.root, self.directory, self.state, 'source-only')
        self.assertEqual(manifest['photoCount'], 2)
        self.assertEqual(manifest['manualSourceCount'], 1)
        self.assertEqual(manifest['manualSourcePeopleCount'], 1)
        source = manifest['manualSources'][0]
        self.assertEqual(source['personId'], 't5')
        self.assertFalse(source['eligibleForLive'])
        self.assertIsNone(source['gameSha256'])
        self.assertEqual(source['stageImages'], {})
        self.assertTrue(source['sourceImage']['path'].endswith('.jpg'))
        self.assertEqual(source['sourceImage']['sha256'], candidate['originalSha256'])
        self.assertEqual(len(manifest['manualContactSheets']), 1)
        sha = self._commit()
        published = publish_links(self.root, self.directory, manifest, sha, repository='owner/project')
        image = published['manualSources'][0]['sourceImage']
        self.assertIn('/' + sha + '/', image['rawUrl'])
        self.assertIn('source-only-0001', image['githubViewUrl'])
        markdown = (self.directory / 'review-public/latest.md').read_text()
        self.assertIn('原圖保留', markdown)
        self.assertIn('待裁切人物', markdown)
        self.assertIn('SOURCE_ONLY', markdown)
        self.assertIn('Face is too small', markdown)
        self.assertEqual(self.state['people']['t5']['status'], 'download_failed')
        self.assertFalse((self.directory / 'reviews').exists())


if __name__ == '__main__':
    unittest.main()
