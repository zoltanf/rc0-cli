# Profiles and configuration

`rc0` stores settings in a TOML config file and reads them with the
following precedence (highest wins):

1. Command-line flag (e.g. `--api-url`).
2. Environment variable (e.g. `RC0_API_URL`).
3. Profile section in the config file.
4. Built-in default.

Tokens are **never** written to the config file — see `rc0 help
authentication`.

## Config file location

| Platform  | Path |
|-----------|------|
| macOS/Linux | `$XDG_CONFIG_HOME/rc0/config.toml` (falls back to `~/.config/rc0/config.toml`) |
| Windows   | `%APPDATA%\rc0\config.toml` |

Run `rc0 config path` to see the effective path, `rc0 config show` to
see the effective values (and where each came from).

## Format

```toml
# Default profile — used when --profile is omitted.
[default]
api_url = "https://my.rcodezero.at"
output  = "table"
timeout = 30
retries = 3

# Named profile for a test environment.
[profiles.test]
api_url = "https://my-test.rcodezero.at"
```

## Selecting a profile

```bash
# One-off
rc0 --profile test zone list

# Session default
export RC0_PROFILE=test
rc0 zone list

# Persist by writing to config
rc0 config set api_url https://my-test.rcodezero.at --profile test
```

## Precedence in practice

```bash
# Config says prod; env overrides to test; flag overrides to custom.
export RC0_API_URL=https://my-test.rcodezero.at
rc0 --api-url https://staging.rcodezero.example zone list   # → staging
```
