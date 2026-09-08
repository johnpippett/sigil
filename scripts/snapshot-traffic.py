#!/usr/bin/env python3
"""Capture GitHub repository traffic into an append-only local JSON archive.

The GitHub views and clones endpoints return rolling windows (currently up to
14 days), rather than individual events with stable IDs.  Existing snapshot
files are therefore retained so those windows can be inspected later, but
overlapping windows cannot be deduplicated by this script.  The raw API
responses are kept in each snapshot for that reason.

The command uses the installed ``gh`` executable and its existing
authentication.  It makes two read-only calls::

    gh api repos/OWNER/REPO/traffic/views
    gh api repos/OWNER/REPO/traffic/clones

Usage::

    python scripts/snapshot-traffic.py [--repo OWNER/REPO]
        [--output-dir PATH]

The default repository is ``johnpippett/sigil``.  Snapshots are written to
``~/.local/state/sigil/traffic`` unless ``--output-dir`` is supplied.  The
output directory is outside the tracked repository by default.  Each output
file contains ``captured_at``, ``repo``, and the raw ``views`` and ``clones``
responses, and is published atomically.  API failures are reported
with their ``gh`` error text and no partial snapshot is created.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile


DEFAULT_REPO = "johnpippett/sigil"
DEFAULT_OUTPUT_DIR = Path.home() / ".local" / "state" / "sigil" / "traffic"
TRAFFIC_ENDPOINTS = ("views", "clones")


class SnapshotError(RuntimeError):
    """An expected failure while collecting or writing a snapshot."""


def _error_details(result):
    """Return useful gh output without logging the command or any credentials."""
    stderr = getattr(result, "stderr", "") or ""
    stdout = getattr(result, "stdout", "") or ""
    return str(stderr).strip() or str(stdout).strip()


def _fetch_api_json(repo, endpoint):
    """Fetch one raw traffic response through ``gh api``."""
    api_endpoint = "repos/{}/traffic/{}".format(repo, endpoint)
    command = ["gh", "api", api_endpoint]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = _error_details(exc)
        message = "gh api {} failed with exit status {}".format(
            api_endpoint, exc.returncode
        )
        if details:
            message += ": " + details
        raise SnapshotError(message) from exc
    except OSError as exc:
        raise SnapshotError(
            "unable to run gh api {}: {}".format(api_endpoint, exc)
        ) from exc

    try:
        return json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SnapshotError(
            "gh api {} did not return valid JSON: {}".format(api_endpoint, exc)
        ) from exc


def collect_traffic(repo=DEFAULT_REPO):
    """Return raw ``views`` and ``clones`` API responses for ``repo``."""
    return {
        endpoint: _fetch_api_json(repo, endpoint)
        for endpoint in TRAFFIC_ENDPOINTS
    }


def _captured_at():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _snapshot_path(output_dir, captured_at):
    """Choose a unique, date-timestamped path without replacing old data."""
    safe_timestamp = captured_at.replace(":", "-")
    path = output_dir / (safe_timestamp + ".json")
    suffix = 1
    while path.exists():
        path = output_dir / (safe_timestamp + "-{}.json".format(suffix))
        suffix += 1
    return path


def write_snapshot(repo, traffic, output_dir=DEFAULT_OUTPUT_DIR, captured_at=None):
    """Atomically append one JSON snapshot and return its path.

    Existing files are never removed or overwritten.  Keeping every capture
    preserves the overlapping rolling windows returned by GitHub.
    """
    output_dir = Path(output_dir).expanduser()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SnapshotError(
            "could not prepare traffic snapshot directory {}: {}".format(
                output_dir, exc
            )
        ) from exc
    captured_at = captured_at or _captured_at()
    snapshot_path = _snapshot_path(output_dir, captured_at)
    payload = {
        "captured_at": captured_at,
        "repo": repo,
        "views": traffic["views"],
        "clones": traffic["clones"],
    }

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(output_dir),
            prefix=".traffic-snapshot-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(payload, temporary_file, indent=2, sort_keys=True)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_path, 0o600)
        # Linking the complete temporary file into place is atomic and fails
        # rather than replacing a same-timestamp file created concurrently.
        while True:
            try:
                os.link(temporary_path, snapshot_path)
            except FileExistsError:
                snapshot_path = _snapshot_path(output_dir, captured_at)
            else:
                os.unlink(temporary_path)
                temporary_path = None
                break
    except OSError as exc:
        raise SnapshotError(
            "could not write traffic snapshot {}: {}".format(snapshot_path, exc)
        ) from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass

    return snapshot_path


def snapshot(repo=DEFAULT_REPO, output_dir=DEFAULT_OUTPUT_DIR):
    """Collect both endpoints and atomically append one traffic snapshot."""
    traffic = collect_traffic(repo)
    return write_snapshot(repo, traffic, output_dir=output_dir)


def build_parser():
    description = (
        "Capture raw GitHub views and clones responses. GitHub returns rolling "
        "windows of up to 14 days, so retained snapshots overlap and cannot "
        "be deduplicated by this tool."
    )
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="GitHub repository in OWNER/REPO form (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "directory for retained timestamped JSON snapshots "
            "(default: %(default)s)"
        ),
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        snapshot_path = snapshot(repo=args.repo, output_dir=args.output_dir)
    except SnapshotError as exc:
        print("snapshot-traffic: {}".format(exc), file=sys.stderr)
        return 1
    print(snapshot_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
