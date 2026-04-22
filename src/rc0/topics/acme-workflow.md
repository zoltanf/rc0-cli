# ACME DNS-01 Workflow

ACME DNS-01 validation lets a certificate authority verify domain ownership by
checking for a specific TXT record at `_acme-challenge.<zone>.`. `rc0 acme`
automates adding and removing those records against the RcodeZero v1 ACME API.

## Token permission

ACME endpoints (`/api/v1/acme/...`) require an API token with the **ACME**
permission. A standard read/write token will receive a 403. Create or update
your token at <https://my.rcodezero.at/>.

## Commands

```
rc0 acme zone-exists <zone>          # Confirm the zone is ACME-configured
rc0 acme list-challenges <zone>      # List current _acme-challenge. TXT records
rc0 acme add-challenge <zone> --value TOKEN [--ttl 60]
rc0 acme remove-challenge <zone>     # Removes all _acme-challenge. TXT records
```

## Typical certbot hook workflow

**auth hook** (`/etc/letsencrypt/renewal-hooks/auth/rc0-acme.sh`):

```bash
#!/usr/bin/env bash
rc0 acme add-challenge "$CERTBOT_DOMAIN" --value "$CERTBOT_VALIDATION"
sleep 10   # allow propagation
```

**cleanup hook** (`/etc/letsencrypt/renewal-hooks/cleanup/rc0-acme.sh`):

```bash
#!/usr/bin/env bash
rc0 --yes acme remove-challenge "$CERTBOT_DOMAIN"
```

## Dry-run

Both mutations support `--dry-run` (or `RC0_DRY_RUN=1`) to preview the
request without making any API call:

```bash
rc0 --dry-run acme add-challenge example.com --value testtoken123
rc0 --dry-run acme remove-challenge example.com
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 5 | 403 — token lacks the ACME permission |
| 6 | 404 — zone not found or not ACME-configured |
| 12 | Confirmation declined |
