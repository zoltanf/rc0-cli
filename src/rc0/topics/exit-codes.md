# Exit codes

Every `rc0` command returns a specific exit code. Scripts can rely on them.

| Code | Meaning |
|------|---------|
|    0 | Success (including successful `--dry-run`) |
|    1 | Generic error (minimised; rc0 prefers a specific code) |
|    2 | Usage error (bad flags, missing arguments) |
|    3 | Config error (no token, bad config file) |
|    4 | Authentication error (HTTP 401) |
|    5 | Authorization / permission error (HTTP 403) |
|    6 | Not found (HTTP 404) |
|    7 | Validation error (HTTP 400 or client-side) |
|    8 | Conflict / already exists (HTTP 409) |
|    9 | Rate limited (HTTP 429) |
|   10 | Network / timeout / DNS failure |
|   11 | Server error (HTTP 5xx after retries) |
|   12 | Confirmation declined by user |
|  130 | Interrupted (SIGINT) |

## Dry-run

`--dry-run` always exits 0 on success. Scripts can detect dry-run by the
presence of the `"dry_run": true` field in JSON output when `-o json`.

## Machine-readable errors

With `-o json`, errors are written as JSON to **stderr** with the shape:

```json
{
  "error": {
    "code": "ZONE_ALREADY_EXISTS",
    "message": "Zone example.com is already configured.",
    "http_status": 409,
    "hint": "Run `rc0 zone show example.com` to inspect.",
    "request": {"method": "POST", "url": "https://...", "id": "abc-..."}
  }
}
```

Scripts should use exit code as the source of truth; the JSON is a
diagnostic aid.
