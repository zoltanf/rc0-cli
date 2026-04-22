# Dry-run

Every rc0 command that changes state supports `--dry-run`. A dry-run never
contacts the API. It prints the HTTP request the command **would** have sent,
in enough detail to reproduce exactly — method, URL, redacted headers, JSON
body, and an English summary.

The exit code is `0` on success (mission-plan §18.1 Option A, matches `gh` and
`terraform plan`). Tell dry-runs apart from real runs by the `"dry_run": true`
field in `-o json` output.

## Human output

```
$ rc0 zone create example.com --type master --master 10.0.0.1 --dry-run
Would create master zone example.com with 1 master IP(s).

  POST https://my.rcodezero.at/api/v2/zones
  Authorization: Bearer ***REDACTED***
  Content-Type: application/json

  {
    "domain": "example.com",
    "type": "master",
    "masters": ["10.0.0.1"]
  }
```

## Machine output

```
$ rc0 zone create example.com --type master --dry-run -o json
{
  "dry_run": true,
  "request": {
    "method": "POST",
    "url": "https://my.rcodezero.at/api/v2/zones",
    "headers": {
      "Authorization": "Bearer ***REDACTED***",
      "Content-Type": "application/json"
    },
    "body": {"domain": "example.com", "type": "master"}
  },
  "summary": "Would create master zone example.com.",
  "side_effects": ["creates_zone"]
}
```

## `--dry-run` vs. `rc0 zone test`

They are different.

- `--dry-run` is a **client-side preview**. No network call. Exits 0.
- `rc0 zone test <domain>` hits `POST /api/v2/zones?test=1`. The API validates
  the would-be zone (domain syntax, conflicts, masters reachability) and returns
  its own errors. The zone is not created.

You can combine them:

```
$ rc0 zone test example.com --type master --dry-run -o json
```

…prints the HTTP request that `zone test` would have sent.

## Confirmations

Destructive commands prompt by default (mission-plan §7). `--dry-run` bypasses
the prompt — there is nothing to destroy — and so does `--yes` / `-y`. Exit
code `12` means the user declined. Exit code `0` means the dry-run printed.

## Parity guarantee

Every rc0 release runs a parity test against its own mutation surface: the
dry-run request body and URL are byte-identical to the request sent on the
live path (see `tests/unit/test_dry_run_parity.py`). If you script against
dry-run output, the real call will look the same.
