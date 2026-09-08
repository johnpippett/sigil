import contextlib
import importlib.machinery
import importlib.util
import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('sigil', str(ROOT / 'sigil'))
spec = importlib.util.spec_from_loader(loader.name, loader)
sigil = importlib.util.module_from_spec(spec)
loader.exec_module(sigil)
A, B = 'a' * 64, 'b' * 64


def pypi(*hashes):
    return {'urls': [{'filename': 'pkg.whl', 'packagetype': 'bdist_wheel',
                      'digests': {'sha256': h}} for h in hashes]}


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache_patch = patch.object(sigil, 'CACHE_DIR', Path(self.temp.name) / 'sigil')
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)

    def run_cli(self, args, response):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sigil.sys, 'argv', ['sigil'] + args), \
             patch.object(sigil, 'fetch_json', return_value=response) as fetch, \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                sigil.main()
                code = 0
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue(), fetch

    def test_gem_uses_pinned_endpoint(self):
        with patch.object(sigil, 'fetch_json', return_value={'number': '13.0.6', 'sha': A}) as fetch:
            self.assertEqual(sigil.resolve_hash('gem', 'rake', '13.0.6', {})[0], A)
        fetch.assert_called_once_with('https://rubygems.org/api/v2/rubygems/rake/versions/13.0.6.json')

    def test_gem_mismatch_fails_even_with_stale_cache(self):
        cache = {'rake==13.0.6': {'hash': A, 'ts': 0}}
        with contextlib.redirect_stderr(io.StringIO()), patch.object(sigil, 'fetch_json', return_value={'number': '13.4.2', 'sha': B}):
            self.assertIsNone(sigil.resolve_hash('gem', 'rake', '13.0.6', cache)[0])

    def test_gem_missing_version_fails(self):
        with contextlib.redirect_stderr(io.StringIO()), patch.object(sigil, 'fetch_json', return_value={'sha': A}):
            self.assertIsNone(sigil.resolve_hash('gem', 'rake', '13.0.6', {})[0])

    def test_pip_emits_all_distinct_artifact_hashes_and_preserves_extras(self):
        code, out, _, _ = self.run_cli(['pip', 'httpx[http2]==0.28.1'], pypi(A, B, A))
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), f'httpx[http2]==0.28.1 --hash=sha256:{A} --hash=sha256:{B}')

    def test_pip_extras_not_sent_to_registry(self):
        _, _, _, fetch = self.run_cli(['pip', 'httpx[http2]==0.28.1'], pypi(A))
        fetch.assert_called_once_with('https://pypi.org/pypi/httpx/0.28.1/json')

    def test_pip_legacy_single_hash_cache_is_refreshed(self):
        cache = {'httpx==0.28.1': {'hash': A, 'ts': time.time()}}
        with patch.object(sigil, 'fetch_json', return_value=pypi(A, B)) as fetch:
            hashes, _ = sigil.resolve_hash('pip', 'httpx', '0.28.1', cache)
        self.assertEqual(hashes, [A, B])
        fetch.assert_called_once()

    def test_pip_malformed_schema_fails_without_traceback(self):
        for response in [[], {'urls': 'bad'}, {'urls': [None]}, pypi('bad')]:
            with self.subTest(response=response):
                code, out, _, fetch = self.run_cli(['pip', 'httpx==0.28.1'], response)
                self.assertEqual(code, 1)
                self.assertEqual(out, '')
                fetch.assert_called_once()

    def test_scoped_npm_url_and_output(self):
        h = 'sha512-YWJjZA=='
        code, out, _, fetch = self.run_cli(['npm', '@angular/core@17.0.0'], {'dist': {'integrity': h}})
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), f'@angular/core@17.0.0  integrity:{h}')
        fetch.assert_called_once_with('https://registry.npmjs.org/%40angular%2Fcore/17.0.0')

    def test_failed_lookup_not_retried_and_no_partial_output(self):
        code, out, _, fetch = self.run_cli(['cargo', 'ripgrep==14.1.1'], None)
        self.assertEqual(code, 1)
        self.assertEqual(out, '')
        fetch.assert_called_once()

    def test_fresh_cache_avoids_api(self):
        cache = {'ripgrep==14.1.1': {'hash': A, 'ts': time.time()}}
        with patch.object(sigil, 'fetch_json') as fetch:
            self.assertEqual(sigil.resolve_hash('cargo', 'ripgrep', '14.1.1', cache), (A, 'cache-fresh'))
        fetch.assert_not_called()

    def test_stale_cache_warns_when_offline(self):
        err = io.StringIO()
        with patch.object(sigil, 'fetch_json', return_value=None), contextlib.redirect_stderr(err):
            result = sigil.resolve_hash('cargo', 'ripgrep', '14.1.1', {'ripgrep==14.1.1': {'hash': A, 'ts': 0}})
        self.assertEqual(result, (A, 'cache-stale'))
        self.assertIn('cached hash', err.getvalue())

    def test_invalid_cache_timestamp_is_ignored(self):
        for timestamp in ['invalid', 10**400, float('nan'), float('inf'), -1, True]:
            with self.subTest(timestamp=timestamp), patch.object(
                sigil, 'fetch_json', return_value={'version': {'checksum': B}}
            ):
                result = sigil.resolve_hash('cargo', 'ripgrep', '14.1.1', {
                    'ripgrep==14.1.1': {'hash': A, 'ts': timestamp}
                })
            self.assertEqual(result, (B, 'api'))

    def test_multi_package_failure_emits_nothing(self):
        out = io.StringIO()
        with patch.object(sigil.sys, 'argv', ['sigil', 'cargo', 'one==1', 'two==2']), \
             patch.object(sigil, 'fetch_json', side_effect=[{'version': {'checksum': A}}, None]), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as failure:
                sigil.main()
        self.assertEqual(failure.exception.code, 1)
        self.assertEqual(out.getvalue(), '')

    def test_non_object_cache_is_ignored(self):
        sigil.CACHE_DIR.mkdir()
        (sigil.CACHE_DIR / sigil.REGISTRIES['pip']['cache_file']).write_text('[]')
        self.assertEqual(sigil.load_cache('pip'), {})

    def test_cache_roundtrip_and_permissions(self):
        cache = {'httpx==0.28.1': {'hash': [A, B], 'ts': time.time()}}
        sigil.save_cache('pip', cache)
        self.assertEqual(sigil.load_cache('pip'), cache)
        self.assertEqual(sigil.CACHE_DIR.stat().st_mode & 0o777, 0o700)
        self.assertEqual((sigil.CACHE_DIR / sigil.REGISTRIES['pip']['cache_file']).stat().st_mode & 0o777, 0o600)

    def test_help_uses_sigil_name(self):
        _, _, err, _ = self.run_cli(['--help'], None)
        self.assertIn('Usage: sigil ', err)
        self.assertNotIn('pkg-hash-resolve', err)


if __name__ == '__main__':
    unittest.main()
