```
  ███████╗ ██╗  ██████╗ ██╗ ██╗
  ██╔════╝ ██║ ██╔════╝ ██║ ██║
  ███████╗ ██║ ██║  ███╗██║ ██║
  ╚════██║ ██║ ██║   ██║██║ ██║
  ███████║ ██║ ╚██████╔╝██║ ███████╗
  ╚══════╝ ╚═╝  ╚═════╝ ╚═╝ ╚══════╝

       inspect before install
```

---

# Sigil

**A zero-dependency package hash resolver for Python 3.9+.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-3670A0)](https://python.org)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)]()
[![Registries](https://img.shields.io/badge/registries-4-purple)]()

Sigil asks PyPI, crates.io, RubyGems, or npm for the hash published for an exact package version, validates the returned format, caches the result for 24 hours, and prints it in a package-manager-friendly format.

Sigil does not download or install packages, and it does not enforce verification by itself. Use the package manager's hash, checksum, or lockfile controls to enforce the result during installation.

A registry hash answers whether downloaded bytes match the bytes described by registry metadata. It does not establish that the package is safe, that its source is benign, or that the registry itself has not been compromised.

## How It Works

1. You provide a package name and an exact version.
2. Sigil requests metadata over HTTPS from the package registry.
3. It validates the hash format and writes the result to its local cache.
4. It prints the hash for you to record or pass to the package manager's verification mechanism.

Fresh cache entries avoid a network request. The cache lives under `~/.cache/sigil/`; entries are refreshed after 24 hours. If a registry is unavailable, an older valid entry may be used with a warning.

## Registries

| Registry | Command | Hash output |
|----------|---------|-------------|
| **PyPI** | `sigil pip httpx==0.28.1` | SHA-256 for every release file, in requirements format |
| **crates.io** | `sigil cargo ripgrep==14.1.1` | SHA-256 checksum lookup |
| **RubyGems** | `sigil gem rake==13.2.1` | SHA-256 gem hash lookup |
| **npm** | `sigil npm cowsay@1.6.0` | SRI value from `dist.integrity` |

Scoped npm names are supported, for example `sigil npm @angular/core@17.0.0`.

## Quick Start

```bash
# Clone the repository (Python 3.9+; standard library only)
git clone https://github.com/johnpippett/sigil.git
cd sigil
chmod +x sigil

# Resolve an exact package version
./sigil pip httpx==0.28.1
./sigil cargo ripgrep==14.1.1
./sigil gem rake==13.2.1
./sigil npm cowsay@1.6.0
./sigil npm @angular/core@17.0.0
```

For pip, Sigil emits one requirements-style line per requested package, with every distinct release-file hash on that line as a `--hash` flag. A standalone example uses `six`, which has no runtime dependencies:

```bash
./sigil pip six==1.17.0 > requirements-hashes.txt && \
  python -m pip install --require-hashes -r requirements-hashes.txt
```

For a dependency graph, build a complete, fully pinned lock file containing every direct and transitive dependency and its hashes before running pip. Sigil resolves only the packages named on its command line; pip will reject an incomplete hash-checked requirements file. Do not install missing dependencies separately without hashes.

For cargo, RubyGems, and npm, the commands above only look up and print the registry value. Verify the exact artifact or use the package manager's documented checksum or lockfile support before installing or executing it.

## Optional Hermes Agent Integration

This repository includes an optional skill file for [Hermes Agent](https://github.com/NousResearch/hermes-agent). It teaches the agent to call Sigil before package operations; it does not change package-manager behavior or provide enforcement on its own.

```bash
mkdir -p ~/.hermes/skills/software-development/sigil/scripts
cp SKILL.md ~/.hermes/skills/software-development/sigil/SKILL.md
cp SECURITY.md ~/.hermes/skills/software-development/sigil/SECURITY.md
cp sigil ~/.hermes/skills/software-development/sigil/scripts/sigil
```

## Security

Sigil validates package names, versions, and registry hash formats; encodes registry URL path components; and writes cache entries atomically with restrictive permissions. These checks protect the resolver and its output from malformed metadata. They do not replace review of package code or the package manager's own verification controls.

See [SECURITY.md](SECURITY.md) for the threat model and limitations.

## Feedback

If you use Sigil, find a bug, or have a package-manager workflow to share, [open a GitHub issue](https://github.com/johnpippett/sigil/issues/new) with the command, registry, and expected behavior.

## Maintainer Checks

Run the standard-library test suite with:

```bash
python -m unittest discover -s tests -v
```

To retain a read-only GitHub traffic snapshot, use an authenticated `gh` CLI:

```bash
python scripts/snapshot-traffic.py --repo johnpippett/sigil
```

Snapshots are retained under `~/.local/state/sigil/traffic/` by default. GitHub returns rolling traffic windows, so keeping periodic snapshots makes later comparison possible.

## License

MIT © John Pippett
