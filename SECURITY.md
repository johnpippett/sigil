# Security — Sigil

## Threat Model

Sigil operates at the boundary between package registries and your system. Its threat model assumes:

1. **The registry APIs are trusted** — Sigil fetches hashes from PyPI, crates.io, RubyGems, and npm. If a registry is fully compromised, no hash verifier can save you.
2. **HTTPS protects transit** — API calls use TLS. Sigil does not implement its own certificate pinning (stdlib `urllib` uses system CA trust).
3. **Local attacker with filesystem access is out of scope** — If an attacker can write to your `~/.cache/hermes/`, they own your user account.

## Attack Surface

### Hash value injection (BLOCKED)

A compromised registry response containing a hash with embedded newlines:
```json
{"sha256": "abc123\nbackdoor==99.0.0 --hash=sha256:aaaa..."}
```
Would cause pip to parse two separate packages. **Blocked** by `validate_hash()` — rejects any hash containing control characters, whitespace, or non-hex characters (for SHA256 registries) or non-SRI format (for npm).

### Version string injection (BLOCKED)

A compromised registry returning a version with embedded newlines:
```json
{"version": "1.0.0\nbackdoor==99.0.0"}
```
Would cause the output to contain two lines. **Blocked** by `validate_identifier()` on all version strings from registry APIs.

### Package name injection (BLOCKED)

User-supplied package names are validated via `validate_identifier()` before use in output. Registry-returned names are not used in output (only in API URLs).

### Cache poisoning (MITIGATED)

Cache files are written atomically (`tempfile` + `fsync` + `os.replace`) with permissions `0o600`. Cache directory is `0o700`. Concurrent writes cannot corrupt the cache. Cache entries include timestamps and are re-verified after 24h TTL.

### Shell injection via cargo/gem variables (FALSE POSITIVE)

The pattern `echo "$HASH  file" | sha256sum -c` used in the skill's install recipes uses double-quoted variable expansion. Bash does NOT recursively expand `$()` inside variable values — the `$()` is treated as a literal string. Tested and confirmed.

### API schema changes (GRACEFUL DEGRADATION)

If a registry changes its JSON response format, `extract_hash()` returns None. Sigil then falls back to the cached hash (if available) with a warning, or refuses to install (if no cache exists). The 24h TTL ensures stale caches are refreshed regularly, catching schema changes during normal operation.

## What Sigil Does NOT Protect Against

- **Compromised registry infrastructure** — If PyPI itself is serving malicious packages with correct hashes, hash verification is meaningless.
- **Dependency confusion / namespace attacks** — Installing the wrong package with the right hash is still wrong. Use scoped registries and `--index-url` for this.
- **Malicious source code** — A crate can be malicious even if its `.crate` file hash matches. Sigil verifies artifact integrity, not code safety.
- **Local privilege escalation** — If an attacker has write access to your system, they can modify Sigil or pip itself.

## Responsible Disclosure

Found a vulnerability? Open an issue or email the maintainer directly. Sigil is a security tool — security bugs get priority treatment.
