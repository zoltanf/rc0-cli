# Pagination

List commands accept three flags to navigate multi-page responses:

| Flag | Purpose |
|------|---------|
| `--page N`      | 1-indexed page number. Default: `1`. |
| `--page-size N` | Rows per page. Default: `50`. Maximum: `1000`. |
| `--all`         | Auto-paginate: fetch every page and return one combined result. |

`--all` is incompatible with `--page` — pick one. `--page-size` tunes the
batch size for both modes.

## Under the hood

The RcodeZero API mixes two response shapes. `rc0`'s paginator handles both
transparently:

- **Laravel envelope** — `/api/v2/zones`, `/zones/{zone}/rrsets`,
  `/messages/list`, `/reports/problematiczones`. Pages are identified by
  `current_page` + `last_page` in the envelope.
- **Bare JSON array** — `/api/v2/tsig`, `/stats/*`, most `/reports/*`. The
  paginator stops when a page returns fewer rows than `--page-size`.

## Examples

```bash
# First 50 zones
rc0 zone list

# Specific page
rc0 zone list --page 2 --page-size 25

# Every zone in the account
rc0 zone list --all

# Combine --all with filters
rc0 record list example.com --all --name www.example.com. --type A
```

## Deterministic ordering

Within a single response the API returns rows in a documented order
(typically by `domain` or `id`). `--all` preserves that order while
aggregating pages. Scripts may rely on consecutive `rc0` invocations
returning the same row order for unchanged data.
