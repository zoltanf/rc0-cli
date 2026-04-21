# rc0

> The command line for RcodeZero DNS.

`rc0` is a first-class command-line interface for the
[RcodeZero Anycast DNS API](https://my.rcodezero.at/openapi/) — safe by
default, scriptable for agents, and feature-complete for humans.

**Status:** pre-alpha (v0.1.0 bootstrap). Do not use for production zones yet.

## Quickstart (placeholder — filled in during Phase 7)

```bash
# Install (once published)
pip install rc0-cli              # or: uv tool install rc0-cli
brew install zoltanf/rc0/rc0     # macOS / Linuxbrew (once tap is live)

# Authenticate
rc0 auth login

# Safe-by-default operations
rc0 zone list
rc0 zone create example.com --type master --dry-run
```

See [docs/rc0-cli-mission-plan.md](docs/rc0-cli-mission-plan.md) for the
authoritative design and feature map.

## License

MIT — see [LICENSE](LICENSE).
