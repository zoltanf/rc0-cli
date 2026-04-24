# Pagination

List commands fetch **every** row by default. No flag is required — you get
the complete result set automatically.

| Flag | Purpose |
|------|---------|
| `--page N`      | Fetch only this 1-indexed page. Omit to fetch everything. |
| `--page-size N` | Rows per HTTP request. Default: `50` (`100` for ACME). Max: `1000`. |
| `--all`         | Kept for script compatibility. Same as omitting every flag. |

## Why the default changed

Prior releases defaulted to returning only the first 50 rows, with no
indication when more existed. A zone with 200 RRsets and a zone with 50
RRsets looked identical on screen. This caused an operational incident
where records were declared absent because they had been silently paginated
off the first page.

Fetching every page by default is slower on very large zones but cannot
lose data silently.

## `--page` and the safety warning

If you ask for a single page explicitly with `--page N`, `rc0` warns on
stderr when more rows still exist:

    $ rc0 record list example.com --page 1
    …rows…
    warning: showing page 1 of 5 (50 of 237 rows). Omit --page to fetch every row.

`stdout` remains clean (JSON/YAML/CSV output is never polluted by the
warning, so it stays parseable for scripts). Pass `-q` / `--quiet` on the
global flag chain to suppress the warning entirely.

For endpoints that return bare JSON arrays (`tsig list`,
`acme list-challenges`), `rc0` can't know the total from a single response.
When a full page of rows comes back, the warning is phrased accordingly:

    warning: page 3 returned a full page (100 rows); more rows may exist.
    Omit --page to fetch every row.

## Wire-shape details

The RcodeZero API mixes two response shapes; the paginator speaks both:

- **Laravel envelope** — `/api/v2/zones`, `/zones/{zone}/rrsets`,
  `/messages/list`, `/reports/problematiczones`, `/api/v1/acme/zones/*/rrsets`.
  Pages are identified by `current_page` + `last_page` + `total`.
- **Bare JSON array** — `/api/v2/tsig`, `/stats/*`, most `/reports/*`. The
  paginator stops when a page returns fewer rows than `--page-size`.

## Examples

```bash
# Every zone in the account (default behaviour)
rc0 zone list

# Only the second page, 25 rows
rc0 zone list --page 2 --page-size 25

# Filters applied server-side before pagination
rc0 record list example.com --name www.example.com. --type A

# Fewer HTTP round-trips for a giant zone
rc0 record list huge.example --page-size 1000
```

## Deterministic ordering

Within a single response the API returns rows in a documented order
(typically by `domain` or `id`). The default fetch-everything flow
preserves that order while aggregating pages. Scripts may rely on
consecutive `rc0` invocations returning the same row order for unchanged
data.

## Rate limiting on very large result sets

Auto-pagination issues sequential requests with no client-side delay. A
zone with 10 000 RRsets at the default 50/page produces 200 requests. Use
`--page-size 1000` to cut the request count 20× on large zones.
