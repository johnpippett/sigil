---
name: verify-package-hashes
description: Resolve and validate package registry hashes before installation. Use exact versions and the package manager's own hash, checksum, or lockfile controls to enforce the result.
version: 4.0.0
author: Sigil maintainers
license: MIT
metadata:
  tags: [security, supply-chain, hashes, verification, packaging]
---

# Verify Package Hashes

## Overview

Use Sigil to look up the registry hash for an exact package version before installing it. Sigil validates registry metadata, caches valid results for 24 hours, and prints package-manager-friendly output. It does not download or install packages and cannot enforce a hash by itself; the package manager must enforce the value it receives.

The cache is stored under `~/.cache/sigil/`. The user agent is `sigil/4.0.0`. Existing data under previous cache paths is not read or migrated.

## When to use

- Before installing a pinned package from PyPI, crates.io, RubyGems, or npm.
- When recording hashes in a reproducible requirements or lock file.
- When checking that a downloaded artifact matches the hash published by its registry.

Always pin the package name and exact version. A registry hash confirms artifact identity against registry metadata; it does not prove that the package is safe or free of malicious code.

## The script

Examples below assume `sigil` is on `PATH`. From the repository use `./sigil`; for the Hermes installation use `~/.hermes/skills/software-development/sigil/scripts/sigil` in its place.

```bash
sigil REGISTRY PACKAGE[==VERSION] ...
sigil npm PACKAGE[@VERSION] ...

# REGISTRY: pip | cargo | gem | npm
```

Scoped npm names are supported:

```bash
sigil npm @angular/core@17.0.0
```

## PyPI / pip

PyPI publishes hashes for its release artifacts. Sigil emits one requirements-style line per requested package, with every distinct SHA-256 release hash on that line:

```bash
sigil pip httpx==0.28.1 typer==0.16.0
```

To install a standalone no-dependency package with pip's hash enforcement:

```bash
sigil pip six==1.17.0 > requirements-hashes.txt && \
  python -m pip install --require-hashes -r requirements-hashes.txt
```

For a dependency graph, generate or update a complete, fully pinned requirements/lock file before running pip. The command resolves only the packages named on its command line. The file must also contain every transitive dependency, pinned to an exact version with hashes for all artifacts pip may select. Pip rejects an incomplete hash-checked file. Do not install missing dependencies separately without hashes.

## Other registries

These commands perform hash lookups only:

```bash
sigil cargo ripgrep==14.1.1
sigil gem rake==13.2.1
sigil npm cowsay@1.6.0
```

For the resulting value, verify the exact bytes with the package manager's documented checksum or lockfile support before installing or executing the package. Do not treat Sigil's printed value as an installation command.

## Cache and failure behavior

- Fresh entries avoid a registry request for 24 hours.
- An unavailable registry may result in a stale, format-validated cache value with a warning.
- A malformed API response may use a valid cached value with a warning.
- RubyGems missing or different-version metadata is a hard error even if a stale cache entry exists.
- If no valid API or cached value exists, Sigil fails without printing an unverified hash.

## Security

Sigil validates package names, versions, URL path components, and per-registry hash formats. It writes cache files atomically with restrictive permissions. These checks protect the resolver from malformed input and metadata; they do not replace source review, registry trust, or package-manager enforcement.

See [SECURITY.md](SECURITY.md) for the threat model and limitations.

## Common pitfalls

1. **Using an unpinned version.** Resolve and record an exact version before installation.
2. **Hashing only the top-level pip package.** `--require-hashes` requires all direct and transitive dependencies.
3. **Assuming a lookup installs or verifies a package.** Sigil only prints registry metadata.
4. **Treating a matching hash as a malware scan.** A malicious package can have a valid registry hash.
5. **Ignoring stale-cache warnings.** Refresh the lookup when registry state matters.

## Verification checklist

- [ ] Exact package name and version are pinned
- [ ] Hash came from the intended authoritative registry
- [ ] For pip: every direct and transitive dependency is pinned and hashed
- [ ] Package-manager hash, checksum, or lockfile enforcement is enabled
- [ ] The artifact or source is appropriate for the project
- [ ] A mismatch or missing hash stops the installation
