# rc0

> The command line for RcodeZero DNS.

`rc0` is a production-grade CLI for the [RcodeZero Anycast DNS API](https://my.rcodezero.at/openapi/) —
safe by default, scriptable, and feature-complete.

## Install

```bash
# Python (recommended)
pip install rc0-cli
# or
uv tool install rc0-cli

# macOS / Linux via Homebrew (once tap is live)
brew install zoltanf/rc0/rc0

# Pre-built binary — download from GitHub Releases
# https://github.com/zoltanf/rc0-cli/releases/latest
```

## Quickstart

```bash
# 1. Authenticate (stores token in OS keyring)
rc0 auth login

# 2. List your zones
rc0 zone list

# 3. Preview a zone creation without touching the API
rc0 zone create example.com --type master --dry-run

# 4. Add an A record (prompts for confirmation)
rc0 record add example.com --name www --type A --value 198.51.100.1 --ttl 300

# 5. Sign a zone with DNSSEC
rc0 dnssec sign example.com --dry-run

# 6. Manage ACME DNS-01 challenge records
rc0 acme add-challenge example.com --value <token>
rc0 acme remove-challenge example.com
```

All commands support `--output json|yaml|table|csv|tsv` and `--dry-run`.

## Documentation

- [Mission plan & full command reference](docs/rc0-cli-mission-plan.md)
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).
