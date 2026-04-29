# RRset input formats

`rc0 record` commands send DNS resource record sets (RRsets) to the
RcodeZero API. An RRset is a group of records that share the same name,
class, and type. There are three ways to supply RRset data to the CLI,
depending on which command you are running.

## Flag-based input

Used by `record set`, `record append`, and `record delete`. Specify one
RRset per invocation with `--name`, `--type`, `--ttl`, and one or more
`--content` flags. Repeat `--content` to aggregate multiple records into
the same RRset.

```
# Create or replace the www A RRset (upsert):
rc0 record set example.com. \
    --name www \
    --type A \
    --ttl 300 \
    --content 203.0.113.10 \
    --content 203.0.113.11

# Strict create-only (fails if the RRset already exists):
rc0 record set example.com. \
    --name www \
    --type A \
    --content 203.0.113.10 \
    --require-absent

# Strict replace-only (fails if the RRset does not exist):
rc0 record set example.com. \
    --name www \
    --type A \
    --content 203.0.113.10 \
    --require-exists

# Add an MX record without losing the existing ones:
rc0 record append example.com. \
    --name @ \
    --type MX \
    --content "20 backup-mail.example.com."

# Delete the www A RRset (prompts y/N):
rc0 record delete example.com. --name www --type A
```

`record set` is the default upsert verb — it works whether or not the
RRset already exists. `record append` is the safe non-destructive verb;
it fetches the current RRset, deduplicates by content, and writes the
merged set back. To grow an SPF record, add a verification token, or
add a backup MX, reach for `append`.

## JSON/YAML file input (`--from-file`)

Used by `record apply` and `record import`. The file must be a list of
objects. The exact schema depends on the command:

**For `record apply` (PATCH):** each item must include `changetype`.
Valid values are `add`, `update`, and `delete`.

```json
[
  {
    "name": "www.example.com.",
    "type": "A",
    "ttl": 300,
    "changetype": "add",
    "records": [
      {"content": "203.0.113.10"},
      {"content": "203.0.113.11"}
    ]
  },
  {
    "name": "mail.example.com.",
    "type": "A",
    "ttl": 300,
    "changetype": "delete",
    "records": []
  }
]
```

The same file in YAML:

```yaml
- name: www.example.com.
  type: A
  ttl: 300
  changetype: add
  records:
    - content: 203.0.113.10
    - content: 203.0.113.11

- name: mail.example.com.
  type: A
  ttl: 300
  changetype: delete
  records: []
```

**For `record import --from-file` (PUT):** omit `changetype` — each
item describes the desired final state at that name/type. The API replaces
every RRset in the zone with exactly this list.

```yaml
- name: www.example.com.
  type: A
  ttl: 300
  records:
    - content: 203.0.113.10
- name: example.com.
  type: MX
  ttl: 3600
  records:
    - content: "10 mail.example.com."
```

A `disabled: true` field on any record entry stores the record but hides
it from DNS responses.

## BIND zone-file input (`--zone-file`)

Used by `record import` only. Pass a standard BIND zone file; the
CLI parses it via dnspython and converts every resource record into the
API PUT body. `$ORIGIN` is forced to the zone apex you pass as the first
argument, so a zone file from another toolchain can be applied directly.

```
$ rc0 record import example.com. --zone-file db.example.com
```

Example zone file snippet (`db.example.com`):

```
$ORIGIN example.com.
$TTL    3600

@       IN  SOA ns1.example.com. hostmaster.example.com. (
                2024010101 ; serial
                7200       ; refresh
                3600       ; retry
                604800     ; expire
                60 )       ; minimum

@       IN  NS   ns1.example.com.
@       IN  NS   ns2.example.com.
@       IN  MX   10 mail.example.com.
www     IN  A    203.0.113.10
mail    IN  A    203.0.113.20
```

## Name auto-qualification

Record names in all three input modes follow the trailing-dot rule:

- A name **with** a trailing dot is used as-is (it is already an FQDN).
- A name **without** a trailing dot that equals or ends with the zone
  bare label gets a trailing dot appended.
- A name **without** a trailing dot that is a leaf label gets
  `.<zone>.` appended automatically.
- `@` is expanded to the zone apex.

`record list` accepts the same shorthand on its `--name` filter.

Pass `--verbose` to see a warning for each name that was auto-qualified:

```
$ rc0 record set example.com. --name www --type A --content 203.0.113.10 -v
[warning] auto-qualified name 'www' → 'www.example.com.'
```

## Validation rules

- **TTL** must be ≥ 60 seconds (provider minimum).
- **A** record content must be a valid IPv4 address (dotted-quad).
- **AAAA** record content must be a valid IPv6 address (colon-hex).
- **MX** record content must be `<priority> <exchange>`, where priority
  is an integer in the range 0–65535, e.g. `10 mail.example.com.`
- **PATCH** (`set` / `append` / `delete` / `apply`) accepts at most
  1000 RRset changes per call.
- **PUT** (`import`) accepts at most 3000 RRsets per call.
- **CNAME** cannot share a label with any other record type. A CNAME at
  `www.example.com.` and an A record at the same name in the same batch
  will be rejected client-side before any network call.

## Dry run

Add `--dry-run` to any `record` command to print the request JSON (method,
URL, redacted headers, body) without contacting the API. Exit code is 0.
`record append` still issues the read-only GET to determine the merged
state before producing the dry-run PATCH body.

## Confirmation prompts

- `record delete` — prompts `y/N` before deleting. Pass `-y` to skip.
- `record apply`, `record import`, `record clear` — require typing
  the zone name before proceeding. Pass `-y` to skip.
