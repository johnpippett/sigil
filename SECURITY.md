# Security — Sigil

## Scope and trust model

Sigil resolves the hash that a package registry publishes for an exact package version. It validates and prints that value; it does not download, install, or enforce package-manager verification.

The threat model assumes:

1. When a registry request succeeds, it is delivered over HTTPS and the host's system CA trust is sound. A registry can be unavailable; Sigil then follows its documented cache fallback or failure behavior.
2. The registry's published hash is an accurate description of the artifact it serves. A hash match does not prove that the artifact or its source is safe.
3. A local attacker who can change the Sigil script, the package manager, or files under `~/.cache/sigil/` already controls the user's account and is out of scope.
4. The caller uses the package manager's own hash, checksum, or lockfile controls to verify the exact bytes that will be installed.

## Protections

### Input and URL handling

Package names and versions are rejected when they contain control characters or whitespace. Registry URL path components are percent-encoded before requests are made, including scoped npm names. Returned hashes are checked against the format expected by each registry:

- PyPI, crates.io, and RubyGems: lowercase SHA-256 hex
- npm: subresource integrity (`sha512-…`, `sha384-…`, `sha256-…`, or `sha1-…`)

Malformed registry values are discarded rather than printed.

### Cache integrity

Cache entries are written to `~/.cache/sigil/` with a temporary file, `fsync`, and an atomic rename. The directory is created with mode `0700` and cache files with mode `0600`. Entries carry timestamps and are refreshed after a 24-hour TTL. Legacy data under other cache directories is not read or migrated.

### Registry and API failures

If an API response does not contain the expected field or its schema changes, Sigil warns and can use a still-valid cached value. RubyGems metadata for a missing or different version is an error and is not replaced by a stale cache entry. If the API is unreachable, it may use a stale, format-validated value with an age warning. With no valid API or cached value, it fails instead of printing an unverified hash.

## What Sigil does not protect against

- **A compromised registry or malicious package.** An attacker who controls registry metadata can publish a malicious artifact and a matching hash. Hash verification checks identity, not intent or code safety.
- **Dependency confusion or wrong-package selection.** Pin the package name, version, and intended index or registry.
- **Incomplete dependency verification.** For pip, `--require-hashes` requires every direct and transitive dependency to be pinned and hashed. Sigil does not resolve the dependency graph for you.
- **Package-manager behavior.** Sigil does not control which artifact a package manager downloads or whether it enforces the value it prints. Use the manager's documented verification controls.
- **Local compromise.** An attacker with write access to the script, cache, package manager, or installed files can bypass this tool.

## Responsible disclosure

Please report security issues through [GitHub's security advisory form](https://github.com/johnpippett/sigil/security/advisories/new) when available. For issues that are not sensitive, [open a GitHub issue](https://github.com/johnpippett/sigil/issues/new) with a reproducible example.
