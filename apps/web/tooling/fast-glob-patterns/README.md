# Next ESLint pattern adapter

This private package replaces Micromatch **only for the three methods used by
fast-glob 3.3.1**: `makeRe`, `scan`, and `braces` in expansion mode. Next.js,
`eslint-config-next`, `@next/eslint-plugin-next`, fast-glob traversal and the
ESLint configuration stay unchanged. This is a replacement, not a patched or
renamed release of the vulnerable `braces` library.

Micromatch previously delegated `makeRe` and `scan` to Picomatch 2; the adapter
uses Picomatch 2.3.2. Brace expansion uses the separate maintained
`brace-expansion` 5.0.12 implementation. The npm devDependency key `micromatch`
and override `fast-glob → $micromatch` provide fast-glob's required module name; the installed
package identifies itself as `@sfr/fast-glob-patterns`, version 0.1.0. There is
no original Micromatch or `braces` package/code in this dependency subtree.
Versions and registry integrity hashes are fixed in `package-lock.json`.

Every method rejects patterns exceeding 10,000 UTF-16 code units or 128
unescaped nested braces. Expansion rejects more than 1,000 generated results
before deduplication. An extra sentinel result detects overflow; limits raise
an error instead of silently omitting lint roots. Escaped braces do not count
as nesting. These are intentional limits for ESLint root-directory patterns,
not a claim of full Micromatch compatibility or a general-purpose glob API.
Future changes to Next/fast-glob consumers require reviewing their API usage
and rerunning compatibility/security tests before upgrading.

Install with ordinary `npm ci`, including in the Node 24 Docker build. No audit
exception, version spoofing, production-only scan or global npm setting is used.

```sh
npm ci
npm ls micromatch braces fast-glob picomatch brace-expansion
npm audit --audit-level=high
npm run test -- tests/unit/eslint-glob.test.ts
```

The regression fixture records directory matching from the original fast-glob
3.3.1/Micromatch 4.0.8/braces 3.0.3 tree at `dfbb950aec0b0034a75a94f6a2719cad68bef6b4`.
Tests cover literal/glob/absolute/array roots, nested alternatives, numeric
ranges, extglobs, negation, dot directories and symlinks, the advisory's deep
nesting shape, expansion overflow, installed package identity and unchanged
ESLint rule settings. Synthetic Pages/App violations also exercise Next rules.
This finite fixture is not an exhaustive equivalence proof for every glob.

Reason: [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
reports stack exhaustion in `braces` AST walkers. On 2026-10-03 there is no
published fixed version; Next's plugin still requires fast-glob. See the
[upstream report](https://github.com/micromatch/braces/issues/70) and the
[replacement implementation](https://github.com/juliangruber/brace-expansion).
