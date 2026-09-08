import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "snapshot-traffic.py"
SPEC = importlib.util.spec_from_file_location("snapshot_traffic", SCRIPT)
snapshot_traffic = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(snapshot_traffic)


class SnapshotTrafficTests(unittest.TestCase):
    def _successful_gh(self):
        responses = {
            "repos/johnpippett/sigil/traffic/views": {
                "count": 2,
                "uniques": 1,
                "views": [{"timestamp": "2026-09-08T00:00:00Z", "count": 2}],
            },
            "repos/johnpippett/sigil/traffic/clones": {
                "count": 3,
                "uniques": 2,
                "clones": [{"timestamp": "2026-09-08T00:00:00Z", "count": 3}],
            },
        }

        def run(command, **kwargs):
            endpoint = command[-1]
            return subprocess.CompletedProcess(
                command, 0, json.dumps(responses[endpoint]), ""
            )

        return run, responses

    def test_snapshot_stores_raw_views_and_clones_responses(self):
        run, responses = self._successful_gh()

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            with patch.object(snapshot_traffic.subprocess, "run", side_effect=run) as gh_run:
                snapshot_path = snapshot_traffic.snapshot(output_dir=output_dir)

            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["repo"], "johnpippett/sigil")
            self.assertEqual(payload["views"], responses["repos/johnpippett/sigil/traffic/views"])
            self.assertEqual(payload["clones"], responses["repos/johnpippett/sigil/traffic/clones"])
            self.assertTrue(payload["captured_at"].endswith("Z"))
            self.assertEqual(gh_run.call_count, 2)
            self.assertEqual(
                [call.args[0][-1] for call in gh_run.call_args_list],
                [
                    "repos/johnpippett/sigil/traffic/views",
                    "repos/johnpippett/sigil/traffic/clones",
                ],
            )
            self.assertFalse(list(output_dir.glob("*.tmp")))

    def test_existing_snapshots_are_retained(self):
        run, _ = self._successful_gh()

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            previous = output_dir / "2026-09-07T00-00-00Z.json"
            previous.write_text('{"repo": "johnpippett/sigil"}\n', encoding="utf-8")

            with patch.object(snapshot_traffic.subprocess, "run", side_effect=run):
                snapshot_traffic.snapshot(output_dir=output_dir)

            self.assertTrue(previous.exists())
            self.assertEqual(len(list(output_dir.glob("*.json"))), 2)

    def test_second_api_failure_surfaces_error_and_writes_no_snapshot(self):
        run, _ = self._successful_gh()
        failure = subprocess.CalledProcessError(
            1,
            ["gh", "api", "repos/johnpippett/sigil/traffic/clones"],
            stderr="HTTP 500: Internal Server Error",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            with patch.object(
                snapshot_traffic.subprocess,
                "run",
                side_effect=[
                    run(
                        ["gh", "api", "repos/johnpippett/sigil/traffic/views"]
                    ),
                    failure,
                ],
            ):
                with self.assertRaisesRegex(
                    snapshot_traffic.SnapshotError,
                    "HTTP 500: Internal Server Error",
                ):
                    snapshot_traffic.snapshot(output_dir=output_dir)

            self.assertFalse(list(output_dir.glob("*.json")))

    def test_output_directory_failure_surfaces_as_snapshot_error(self):
        run, _ = self._successful_gh()

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_target = Path(temporary_directory) / "file"
            output_target.write_text("not a directory", encoding="utf-8")
            with patch.object(snapshot_traffic.subprocess, "run", side_effect=run):
                with self.assertRaisesRegex(
                    snapshot_traffic.SnapshotError,
                    "could not prepare traffic snapshot directory",
                ):
                    snapshot_traffic.snapshot(output_dir=output_target)

    def test_api_failure_surfaces_error_and_writes_no_snapshot(self):
        failure = subprocess.CalledProcessError(
            1,
            ["gh", "api", "repos/johnpippett/sigil/traffic/views"],
            stderr="HTTP 403: Resource not accessible by integration",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            with patch.object(
                snapshot_traffic.subprocess, "run", side_effect=failure
            ):
                with self.assertRaisesRegex(
                    snapshot_traffic.SnapshotError,
                    "HTTP 403: Resource not accessible by integration",
                ):
                    snapshot_traffic.snapshot(output_dir=output_dir)

            self.assertFalse(list(output_dir.glob("*.json")))

    def test_invalid_api_json_surfaces_error_and_writes_no_snapshot(self):
        completed = subprocess.CompletedProcess(
            ["gh", "api", "repos/johnpippett/sigil/traffic/views"],
            0,
            "not-json",
            "",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            with patch.object(
                snapshot_traffic.subprocess, "run", return_value=completed
            ):
                with self.assertRaisesRegex(snapshot_traffic.SnapshotError, "valid JSON"):
                    snapshot_traffic.snapshot(output_dir=output_dir)

            self.assertFalse(list(output_dir.glob("*.json")))


if __name__ == "__main__":
    unittest.main()
