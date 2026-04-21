# Authentication

`rc0` authenticates to the RcodeZero API with a bearer token.

## Getting a token

Generate a token at <https://my.rcodezero.at/enduser-tokens>. The token grants
the scopes you select; keep production tokens scoped narrowly.

## `rc0 auth login`

Interactive:

```
$ rc0 auth login
? API token: ********************************
✓ Authenticated. Token stored in keyring.
```

Non-interactive (for automation):

```
$ rc0 auth login --token-value "$RC0_API_TOKEN"
```

## Where the token is stored

Storage backends in preference order:

1. **Environment variable** `RC0_API_TOKEN` — always wins. Best for CI.
2. **OS keyring** — macOS Keychain, Windows Credential Manager, or Secret
   Service (Linux). This is the default for `rc0 auth login`.
3. **`~/.config/rc0/credentials`** — 0600-permissioned TOML. Used only when
   keyring is unavailable or `--file` was passed.

`rc0` **never** writes tokens to `config.toml` and **never** logs their
values. The `Authorization` header is redacted in every log line and every
`--dry-run` output.

## Profiles

Each profile has its own token. `--profile test` selects the `test` profile's
token. Logging out only removes the active profile's token.

```
$ rc0 --profile test auth login
```

## ACME permission

ACME endpoints (`rc0 acme ...`) require a token with the **ACME** permission.
If you get HTTP 403 from an ACME command, verify the token has this scope
alongside the usual ones.

## Checking auth state

```
$ rc0 auth status
Authenticated as profile 'default' using token ending in a1b2 (backend: keyring).
```
