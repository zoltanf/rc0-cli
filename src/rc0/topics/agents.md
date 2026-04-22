# Driving rc0 from scripts and LLM agents

`rc0` is designed as a first-class citizen for automation. Every command that
works interactively also works in a pipeline or as a tool call from an LLM
agent.

## Machine-readable output

Always pass `-o json` in scripts and agent tool calls. This gives you
deterministic, parseable output regardless of terminal width or colour support.

```bash
# List all zones as JSON
rc0 zone list -o json --all

# Add a record and capture the result
rc0 record add example.com --name www --type A --ttl 3600 --content 10.0.0.1 -o json
```

## Exit codes

Every command returns a specific exit code. Check the exit code, not the output
text, to detect success or failure.

```bash
rc0 zone show example.com -o json
if [ $? -ne 0 ]; then
  echo "Zone does not exist or request failed"
fi
```

See `rc0 help exit-codes` for the full table.

## Errors as JSON

With `-o json`, errors are written as JSON to **stderr**:

```json
{
  "error": {
    "code": "ZONE_NOT_FOUND",
    "message": "Zone example.com does not exist.",
    "http_status": 404,
    "hint": "Run `rc0 zone list` to see available zones.",
    "request": {"method": "GET", "url": "https://my.rcodezero.at/api/v2/zones/example.com", "id": "abc-123"}
  }
}
```

Redirect stderr separately if you need to parse errors:

```bash
rc0 zone show missing.example.com -o json 2>err.json
```

## Skipping confirmation prompts

Destructive commands prompt interactively. Pass `-y` / `--yes` to skip:

```bash
rc0 zone delete old.example.com -y -o json
```

## Dry-run before mutating

Use `--dry-run` to capture the intended HTTP request without sending it. The
dry-run record is printed as JSON (or the active output format) and the process
exits 0. Agents can log or validate the intended request before committing.

```bash
rc0 zone create new.example.com --type master --dry-run -o json
```

Output shape:

```json
{
  "dry_run": true,
  "request": {
    "method": "POST",
    "url": "https://my.rcodezero.at/api/v2/zones",
    "headers": {"Authorization": "Bearer ***REDACTED***", "Content-Type": "application/json"},
    "body": {"domain": "new.example.com", "type": "master"}
  },
  "summary": "Would create master zone new.example.com."
}
```

## Enumerating all commands

`rc0 introspect` emits a JSON document listing every command, flag, type,
default, and example. LLM agents can enumerate the full CLI without parsing
help text:

```bash
rc0 introspect -o json
```

## Pagination

Long lists are paginated. Pass `--all` to fetch every page automatically and
emit the full array as a single JSON array:

```bash
rc0 zone list -o json --all | jq '.[] | select(.dnssec == "no") | .domain'
```

See `rc0 help pagination` for page-by-page control.

## Token management in CI

In CI environments, set `RC0_API_TOKEN` instead of using the keyring:

```bash
export RC0_API_TOKEN="your-token-here"
rc0 zone list -o json
```

The token is **never** printed, logged, or included in `--dry-run` output.

## Recommended agent pattern

1. Call `rc0 introspect -o json` once at session start to discover the command
   surface.
2. Use `--dry-run -o json` before any mutation to validate the intended
   request.
3. Check the exit code; parse stderr JSON on non-zero exit.
4. Pass `-y` for unattended destructive operations; log the action before
   running.
