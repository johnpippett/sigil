---
name: verify-package-hashes
description: Use when installing any package via pip, npm, cargo, gem, brew, or other package managers. Verifies cryptographic hashes against known-good sources before every installation — no hash match, no install. Sub-second overhead via local hash cache with TTL-based freshness.
version: 4.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [security, supply-chain, hashes, verification, packaging]
    related_skills: [systematic-debugging]
---

# Verify Package Hashes

## Overview

Package hash verification with sub-second overhead. Uses a local hash cache with 24h TTL-based freshness so the cache never goes stale without detection. For pip, verification is inline via `--require-hashes` — pip checks the hash during its own download, zero extra I/O.

**Resilience guarantees (evergreen):**
- Cache entries include timestamps; re-verified from registry after 24h
- API response schema validated before hash extraction — format changes fall back to cache with warning
- Registry unreachable → falls back to cached hash with warning (age reported)
- Only hard-blocks when NO hash exists anywhere (no cache, API failed, unrecoverable)
- All four registries are free, no-auth, and stable (PyPI, crates.io, RubyGems, npm)

## When to Use

- `pip install` — **mandatory**, pip has no default hash verification
- `npm install` / `npx` — npm verifies `dist.integrity` from lockfile; for `npx` verify first
- `cargo install` — crates.io publishes checksums, cargo doesn't verify them on install
- `gem install` — RubyGems publishes SHA, gem doesn't verify on install
- `apt install` / `brew install` — signed repos; per-package hash checks optional
- `curl ... | sh` — **BLOCKED**, never do this
- `docker pull` — pull by digest, not tag

## The Script

One script, four registries:

```bash
sigil REGISTRY PACKAGE[==VERSION] ...

# REGISTRY: pip | cargo | gem | npm
# Output format tailored for each package manager
```

## Fast Paths

### pip — inline verification (fastest)

```bash
# Resolve + install in one pipeline (hash verified during pip's own download)
pip install --require-hashes -r <(sigil pip httpx==0.28.1 typer==0.16.0)

# With transitive deps, verify top-level only:
pip install --no-deps --require-hashes -r <(sigil pip httpx==0.28.1)
pip install httpx==0.28.1  # deps via pip's HTTPS
```

### cargo — verify checksum before build

```bash
sigil cargo ripgrep==14.1.1
# Download, verify checksum, then build:
HASH=$(sigil cargo ripgrep==14.1.1 2>/dev/null | awk '{print $NF}' | cut -d: -f2)
curl -sLO "https://static.crates.io/crates/ripgrep/ripgrep-14.1.1.crate"
echo "$HASH  ripgrep-14.1.1.crate" | sha256sum -c --status && cargo install --path ./ripgrep-14.1.1
```

### gem — verify SHA before install

```bash
sigil gem rake==13.2.1
HASH=$(sigil gem rake==13.2.1 2>/dev/null | awk '{print $NF}' | cut -d: -f2)
gem fetch rake -v 13.2.1
sha256sum rake-13.2.1.gem | grep -q "$HASH" && gem install ./rake-13.2.1.gem
```

### npx — verify integrity before execution

npm's `npx` downloads and runs without enforcing `dist.integrity`. Use `npm pack` + local verification — same download, actual enforcement:

```bash
# Resolve integrity (cached: 0ms)
INTEGRITY=$(sigil npm cowsay@1.6.0 2>/dev/null | awk '{print $NF}' | cut -d: -f2-)

# Download the tarball (same bytes npx would fetch)
npm pack "cowsay@1.6.0" --silent

# Verify against registry's integrity hash
ALGO=$(echo "$INTEGRITY" | cut -d- -f1)
COMPUTED="$ALGO-$(openssl dgst -"$ALGO" -binary cowsay-1.6.0.tgz | base64 -w0)"
[ "$INTEGRITY" = "$COMPUTED" ] && echo "VERIFIED" && tar -xzf cowsay-1.6.0.tgz && node ./package/bin/cowsay "hello"
```

### npm — verify then lock

```bash
npm install "PACKAGE@VERSION" --save-exact
# lockfile captures dist.integrity — npm verifies on every subsequent install
jq --arg pkg "node_modules/PACKAGE" '.packages[$pkg].integrity' package-lock.json
```

### apt / brew — signed repos

```bash
# apt — GPG-signed repo metadata covers package lists
apt download PACKAGE=VERSION && sha256sum PACKAGE*.deb

# brew — SHA256 in formula, checked automatically on install
brew fetch FORMULA
```

### docker — pull by digest

```bash
docker pull "IMAGE@sha256:DIGEST"  # Always
docker buildx imagetools inspect "IMAGE:TAG" --raw | jq -r '.config.digest'
```

## Hash Mismatch Protocol

On mismatch: **STOP**. Report expected hash, actual hash, and source. Do NOT install.

On "no hash available" (no cache, API failed, no fallback): **STOP**. Tell the user. Let them decide.

## Security

Full threat model, injection vector analysis, and defense-in-depth in `references/security-review.md`. The script validates every hash against per-registry format patterns and rejects any value containing control characters or whitespace — blocking newline injection, shell metacharacters, and format bypass.

## Common Pitfalls

1. **Piping curl to a shell.** #1 supply chain attack vector. Always download, verify, then execute.
2. **`--require-hashes` without hashing transitive deps.** Pip rejects it. Use `--no-deps` for top-level verification.
3. **`npm install` with `--no-lockfile`.** The lockfile IS the hash verification.
4. **Forgetting to pin the version.** "Latest" is a moving target — hashes change.
5. **Assuming cached hashes are forever.** The script re-verifies after 24h. Don't disable the TTL.
6. **Hash algorithm confusion.** PyPI/cargo/gem use SHA256. npm uses subresource integrity (sha512-...). Don't cross-compare.

## Verification Checklist

- [ ] Exact version pinned
- [ ] Hash from authoritative registry API
- [ ] For pip: `--require-hashes` used
- [ ] For npm: lockfile includes `integrity`
- [ ] On mismatch: BLOCKED
- [ ] On no hash: BLOCKED, user decides
