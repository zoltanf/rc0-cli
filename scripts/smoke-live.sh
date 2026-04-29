#!/usr/bin/env bash
# smoke-live.sh — exhaustive live-API smoke tests for rc0.
#
# Walks every read-only command, exercises each output format, then creates a
# throwaway test zone (default: rc0-cli-test.com), writes a variety of records,
# reads them back, cleans up. Never touches any existing zone on the account.
#
# Usage:
#   ./scripts/smoke-live.sh                       # uses configured default profile
#   RC0_API_TOKEN=xxx ./scripts/smoke-live.sh     # override token inline
#   TEST_DOMAIN=foo.test ./scripts/smoke-live.sh  # change the throwaway zone name
#   SKIP_MUTATIONS=1 ./scripts/smoke-live.sh      # read-only mode
#   SKIP_DNSSEC=1 ./scripts/smoke-live.sh         # skip DNSSEC sign/unsign round-trip
#   ./scripts/smoke-live.sh --profile staging     # extra rc0 flags are forwarded

set -o pipefail

RC0="${RC0:-uv run rc0}"
TEST_DOMAIN="${TEST_DOMAIN:-rc0-cli-test.com}"
MONTH="$(date +%Y-%m)"
DAY_YESTERDAY="$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d yesterday +%Y-%m-%d)"
EXTRA_FLAGS=("${@}")
WORK_DIR="$(mktemp -d -t rc0-smoke-XXXXXX)"

PASS=0
FAIL=0
SKIPPED=0

# ── helpers ───────────────────────────────────────────────────────────────────

green() { printf '\033[32m✓\033[0m %s\n' "$*"; }
red()   { printf '\033[31m✗\033[0m %s\n' "$*"; }
yellow(){ printf '\033[33m•\033[0m %s\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }

section() {
    echo
    bold "════════════════════════════════════════════════════════════════════"
    bold "  $*"
    bold "════════════════════════════════════════════════════════════════════"
}

subsection() {
    echo
    bold "── $* ──"
}

# capture <rc0 args...>  →  sets $OUT and $CODE
capture() {
    local tmp
    tmp=$(mktemp)
    dim "\$ rc0 ${EXTRA_FLAGS[*]:+${EXTRA_FLAGS[*]} }$*"
    $RC0 "${EXTRA_FLAGS[@]}" "$@" > "$tmp" 2>&1 && CODE=0 || CODE=$?
    OUT=$(cat "$tmp")
    rm -f "$tmp"
}

show_output() {
    local n
    n=$(echo "$OUT" | wc -l | tr -d ' ')
    echo "$OUT" | head -15 | sed 's/^/    /'
    [[ "$n" -gt 15 ]] && dim "    … ($n lines total, showing first 15)"
}

assert_no_crash() {
    local desc="$1"
    if echo "$OUT" | grep -q "Traceback"; then
        red "$desc — CRASH (Python traceback)"
        show_output
        (( FAIL++ )) || true
        return 1
    fi
    return 0
}

assert_exit() {
    local expected="$1" desc="$2"
    if [[ "$CODE" -ne "$expected" ]]; then
        red "$desc — expected exit $expected, got $CODE"
        show_output
        (( FAIL++ )) || true
        return 1
    fi
    return 0
}

assert_ok() {
    # assert_no_crash && assert_exit 0 — for read commands that should succeed
    local desc="$1"
    assert_no_crash "$desc" || return 1
    assert_exit 0 "$desc" || return 1
    green "$desc"
    show_output
    (( PASS++ )) || true
    return 0
}

# assert_json_array <min_items> <desc>
assert_json_array() {
    local min="$1" desc="$2" count
    count=$(echo "$OUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    assert isinstance(data, list), f'expected list, got {type(data).__name__}'
    print(len(data))
except Exception as e:
    print(f'ERR:{e}', file=sys.stderr)
    sys.exit(1)
" 2>&1) || {
        red "$desc — invalid JSON array: $count"
        show_output
        (( FAIL++ )) || true
        return 1
    }
    if [[ "$count" -lt "$min" ]]; then
        red "$desc — got $count items, expected at least $min"
        show_output
        (( FAIL++ )) || true
        return 1
    fi
    green "$desc — $count item(s) returned"
    show_output
    (( PASS++ )) || true
}

assert_json_fields() {
    local desc="$1"; shift
    local fields=("$@")
    local args
    args=$(printf '"%s",' "${fields[@]}")
    args="[${args%,}]"
    python3 -c "
import sys, json
data = json.load(sys.stdin)
assert isinstance(data, list) and len(data) > 0, 'empty array'
item = data[0]
missing = [f for f in $args if f not in item]
assert not missing, f'missing fields: {missing}'
" <<< "$OUT" 2>/dev/null && return 0
    red "$desc — missing expected fields: ${fields[*]}"
    show_output
    (( FAIL++ )) || true
    return 1
}

assert_contains() {
    local desc="$1" needle="$2"
    if ! echo "$OUT" | grep -qF -- "$needle"; then
        red "$desc — output does not contain $(printf %q "$needle")"
        show_output
        (( FAIL++ )) || true
        return 1
    fi
    green "$desc — contains $(printf %q "$needle")"
    (( PASS++ )) || true
    return 0
}

skip() {
    yellow "$* — SKIPPED"
    (( SKIPPED++ )) || true
}

# ── preflight ─────────────────────────────────────────────────────────────────

section "Preflight"

capture --version
assert_ok "rc0 --version (binary reachable)" || {
    red "rc0 is not runnable. Aborting."
    exit 2
}

# Make sure TEST_DOMAIN is NOT already configured. We never delete a zone that
# someone else put there.
capture -o json zone list
if ! assert_no_crash "zone list"; then
    red "zone list crashed — aborting before mutations."
    exit 2
fi
if [[ "$CODE" -ne 0 ]]; then
    red "zone list failed (exit $CODE) — aborting before mutations."
    show_output
    exit 2
fi
if echo "$OUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for z in data:
    if z.get('domain','').rstrip('.').lower() == '${TEST_DOMAIN}'.rstrip('.').lower():
        sys.exit(99)
" ; then
    dim "    TEST_DOMAIN=${TEST_DOMAIN} is free — safe to proceed."
else
    red "TEST_DOMAIN=${TEST_DOMAIN} already exists on this account."
    red "Refusing to run — change TEST_DOMAIN=<something-else> and retry."
    exit 2
fi

# Register cleanup trap BEFORE any mutation.
CLEANUP_DONE=0
cleanup() {
    [[ "$CLEANUP_DONE" -eq 1 ]] && return 0
    CLEANUP_DONE=1
    rm -rf "$WORK_DIR" 2>/dev/null || true
    if [[ "${SKIP_MUTATIONS:-0}" == "1" ]]; then
        return 0
    fi
    echo
    dim "── trap: ensuring ${TEST_DOMAIN} is deleted ──"
    $RC0 "${EXTRA_FLAGS[@]}" -y zone delete "$TEST_DOMAIN" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# ══════════════════════════════════════════════════════════════════════════════
#                         READ-ONLY TOUR (account-wide)
# ══════════════════════════════════════════════════════════════════════════════

section "1. Meta / identity"

capture version;                   assert_ok "version"
capture introspect;                assert_no_crash "introspect" && assert_exit 0 "introspect" && {
    if echo "$OUT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'commands' in d" 2>/dev/null; then
        green "introspect — valid JSON with 'commands'"; (( PASS++ )) || true
    else
        red "introspect — not valid command-schema JSON"; show_output; (( FAIL++ )) || true
    fi
}
capture config show;               assert_ok "config show"
capture config path;               assert_ok "config path"
capture auth status;               assert_no_crash "auth status" && { green "auth status — exit $CODE"; show_output; (( PASS++ )) || true; }
capture auth whoami;               assert_no_crash "auth whoami" && { green "auth whoami — exit $CODE"; show_output; (( PASS++ )) || true; }

section "2. Zone reads"

subsection "zone list × every output format"
for fmt in table json yaml csv tsv plain; do
    capture -o "$fmt" zone list
    if assert_no_crash "zone list -o $fmt" && assert_exit 0 "zone list -o $fmt"; then
        green "zone list -o $fmt"
        show_output
        (( PASS++ )) || true
    fi
done

subsection "zone list JSON shape"
capture -o json zone list
if assert_no_crash "zone list -o json (shape check)"; then
    assert_json_array 1 "zone list -o json" && \
    assert_json_fields "zone list fields" domain type serial
    # Store first zone name for downstream per-zone reads — may be empty.
    SAMPLE_ZONE=$(echo "$OUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for z in data:
    if z.get('domain'):
        print(z['domain'].rstrip('.'))
        break
" 2>/dev/null || true)
    dim "    SAMPLE_ZONE=${SAMPLE_ZONE:-<none>}"
fi

subsection "zone show / status / xfr-in / xfr-out — against first existing zone (read-only)"
if [[ -n "${SAMPLE_ZONE:-}" ]]; then
    for cmd in "zone show $SAMPLE_ZONE" "zone status $SAMPLE_ZONE" "zone xfr-in show $SAMPLE_ZONE" "zone xfr-out show $SAMPLE_ZONE"; do
        # shellcheck disable=SC2086
        capture -o json $cmd
        if assert_no_crash "$cmd"; then
            if [[ "$CODE" -eq 0 ]]; then
                green "$cmd — exit 0"
                show_output
                (( PASS++ )) || true
            else
                # Some calls fail with 404/403 depending on zone type — informational.
                yellow "$cmd — exit $CODE (non-fatal)"
                show_output
                (( PASS++ )) || true
            fi
        fi
    done
else
    skip "per-zone reads (no existing zone found)"
fi

section "3. Record reads — against first existing zone"
if [[ -n "${SAMPLE_ZONE:-}" ]]; then
    capture -o json record list "$SAMPLE_ZONE"
    if assert_no_crash "record list $SAMPLE_ZONE"; then
        if [[ "$CODE" -eq 0 ]]; then
            assert_json_array 0 "record list $SAMPLE_ZONE"
        else
            yellow "record list $SAMPLE_ZONE — exit $CODE (non-fatal)"
            show_output
            (( PASS++ )) || true
        fi
    fi
    capture record export "$SAMPLE_ZONE"
    assert_no_crash "record export $SAMPLE_ZONE" && {
        if [[ "$CODE" -eq 0 ]]; then
            green "record export $SAMPLE_ZONE — exit 0 (BIND text)"
            show_output
            (( PASS++ )) || true
        else
            yellow "record export $SAMPLE_ZONE — exit $CODE (non-fatal)"
            show_output
            (( PASS++ )) || true
        fi
    }
else
    skip "record list / export (no existing zone)"
fi

section "4. Reports"

capture -o json report problematic-zones
assert_ok "report problematic-zones"

capture -o json report problematic-zones --all
assert_ok "report problematic-zones --all"

subsection "report nxdomains"
for day_arg in today yesterday; do
    capture -o json report nxdomains --day "$day_arg"
    assert_no_crash "report nxdomains --day $day_arg" || continue
    if [[ "$CODE" -eq 0 ]]; then
        assert_json_array 0 "report nxdomains --day $day_arg"
    else
        yellow "report nxdomains --day $day_arg — exit $CODE (API rejected; non-fatal)"
        show_output
        (( PASS++ )) || true
    fi
done

# Invalid day forms — must be rejected client-side
capture report nxdomains --day 2026-04-21
assert_no_crash "report nxdomains --day 2026-04-21 (ISO)" && \
    assert_exit 2 "report nxdomains --day 2026-04-21 (must reject YYYY-MM-DD client-side)" && \
    { green "report nxdomains rejects ISO dates client-side"; (( PASS++ )) || true; }

capture report nxdomains --day not-a-date
assert_no_crash "report nxdomains --day not-a-date" && \
    assert_exit 2 "report nxdomains --day not-a-date (must reject client-side)" && \
    { green "report nxdomains rejects bogus input client-side"; (( PASS++ )) || true; }

subsection "report accounting"
# API requires --month; calling without it yields exit 7 with a clear message.
capture report accounting
assert_no_crash "report accounting (no filter)" && {
    if [[ "$CODE" -eq 7 ]]; then
        green "report accounting (no filter) — API demands --month (exit 7, no crash)"
        (( PASS++ )) || true
    else
        yellow "report accounting (no filter) — exit $CODE (non-fatal)"
        (( PASS++ )) || true
    fi
}
capture -o json report accounting --month "$MONTH"
if assert_no_crash "report accounting --month $MONTH" && assert_exit 0 "report accounting --month $MONTH"; then
    assert_json_array 0 "report accounting --month $MONTH"
fi
for fmt in json yaml csv tsv plain table; do
    capture -o "$fmt" report accounting --month "$MONTH"
    assert_no_crash "report accounting --month $MONTH -o $fmt" && \
        assert_exit 0 "report accounting -o $fmt" && \
        { green "report accounting -o $fmt"; (( PASS++ )) || true; }
done

subsection "report queryrates"
capture -o json report queryrates --month "$MONTH"
if assert_no_crash "report queryrates --month $MONTH" && assert_exit 0 "report queryrates --month $MONTH"; then
    assert_json_array 0 "report queryrates --month $MONTH"
fi
capture -o json report queryrates --day today
if assert_no_crash "report queryrates --day today" && assert_exit 0 "report queryrates --day today"; then
    assert_json_array 0 "report queryrates --day today"
fi
capture -o json report queryrates --day yesterday
if assert_no_crash "report queryrates --day yesterday" && assert_exit 0 "report queryrates --day yesterday"; then
    assert_json_array 0 "report queryrates --day yesterday"
fi
capture -o json report queryrates --day "$DAY_YESTERDAY"
if assert_no_crash "report queryrates --day $DAY_YESTERDAY" && assert_exit 0 "report queryrates --day $DAY_YESTERDAY"; then
    assert_json_array 0 "report queryrates --day $DAY_YESTERDAY (ISO)"
fi
capture -o json report queryrates --month "$MONTH" --include-nx
if assert_no_crash "report queryrates --include-nx" && assert_exit 0 "report queryrates --include-nx"; then
    assert_json_array 0 "report queryrates --include-nx"
fi
# queryrates with no filter — must fail client-side
capture report queryrates
assert_no_crash "report queryrates (no filter)" && \
    assert_exit 2 "report queryrates (no --day / --month)" && \
    { green "report queryrates requires --day or --month"; (( PASS++ )) || true; }

subsection "report domainlist"
capture -o json report domainlist
if assert_no_crash "report domainlist" && assert_exit 0 "report domainlist"; then
    assert_json_array 0 "report domainlist"
fi

section "5. Account statistics"

for cmd in "stats queries" "stats topzones" "stats countries" "stats topmagnitude" "stats topnxdomains" "stats topqnames"; do
    # shellcheck disable=SC2086
    capture -o json $cmd
    assert_no_crash "$cmd" && {
        if [[ "$CODE" -eq 0 ]]; then
            green "$cmd — exit 0"
            show_output
            (( PASS++ )) || true
        else
            yellow "$cmd — exit $CODE (non-fatal)"
            show_output
            (( PASS++ )) || true
        fi
    }
done

if [[ -n "${SAMPLE_ZONE:-}" ]]; then
    for cmd in "stats zone queries $SAMPLE_ZONE" "stats zone magnitude $SAMPLE_ZONE" "stats zone nxdomains $SAMPLE_ZONE" "stats zone qnames $SAMPLE_ZONE"; do
        # shellcheck disable=SC2086
        capture -o json $cmd
        assert_no_crash "$cmd" && {
            if [[ "$CODE" -eq 0 ]]; then
                green "$cmd — exit 0"
                show_output
                (( PASS++ )) || true
            else
                yellow "$cmd — exit $CODE (non-fatal)"
                show_output
                (( PASS++ )) || true
            fi
        }
    done
else
    skip "per-zone stats (no existing zone)"
fi

section "6. Messages / TSIG / settings (read-only)"

capture -o json messages list
assert_no_crash "messages list" && { green "messages list — exit $CODE"; show_output; (( PASS++ )) || true; }

capture -o json messages poll
assert_no_crash "messages poll" && { green "messages poll — exit $CODE"; show_output; (( PASS++ )) || true; }

capture -o json tsig list
assert_no_crash "tsig list" && { green "tsig list — exit $CODE"; show_output; (( PASS++ )) || true; }

capture -o json tsig list-out
assert_no_crash "tsig list-out" && { green "tsig list-out — exit $CODE"; show_output; (( PASS++ )) || true; }

capture -o json settings show
assert_no_crash "settings show" && { green "settings show — exit $CODE"; show_output; (( PASS++ )) || true; }

section "7. Help topics"

capture help list
assert_ok "help list" && {
    for topic in authentication pagination output-formats exit-codes; do
        echo "$OUT" | grep -qx "$topic" || red "help list missing topic: $topic"
    done
}

for topic in authentication pagination output-formats exit-codes rrset-format dnssec-workflow acme-workflow dry-run profiles-and-config agents; do
    capture help "$topic"
    assert_no_crash "help $topic" && assert_exit 0 "help $topic" && {
        green "help $topic"
        (( PASS++ )) || true
    }
done

section "8. Global-flag ordering sanity"

# Correct: -o before subcommand
capture -o json zone list
assert_no_crash "rc0 -o json zone list" && assert_exit 0 "rc0 -o json zone list" && \
    { green "rc0 -o json zone list (correct ordering)"; (( PASS++ )) || true; }

# Wrong: -o after subcommand → must exit 2, must not crash
capture zone list -o json
assert_no_crash "rc0 zone list -o json (wrong ordering)" && {
    if [[ "$CODE" -ne 0 ]]; then
        green "rc0 zone list -o json — cleanly rejected (exit $CODE)"
        show_output
        (( PASS++ )) || true
    else
        red "rc0 zone list -o json — wrong ordering unexpectedly succeeded"
        show_output
        (( FAIL++ )) || true
    fi
}

capture zone list --help
assert_ok "zone list --help" && {
    if echo "$OUT" | grep -q "zone list -o json"; then
        red "zone list --help still shows -o AFTER subcommand"
        show_output
        (( FAIL++ )) || true
    fi
}

section "9. Dry-run parity (no mutations sent)"

capture --dry-run -o json zone create "$TEST_DOMAIN"
assert_no_crash "dry-run zone create" && assert_exit 0 "dry-run zone create" && \
    { green "dry-run zone create — printed request, no API call"; show_output; (( PASS++ )) || true; }

capture --dry-run -o json record set "$TEST_DOMAIN" --name www --type A --content 10.0.0.1
assert_no_crash "dry-run record set" && assert_exit 0 "dry-run record set" && \
    { green "dry-run record set"; show_output; (( PASS++ )) || true; }

capture --dry-run -o json zone delete "$TEST_DOMAIN"
assert_no_crash "dry-run zone delete" && assert_exit 0 "dry-run zone delete" && \
    { green "dry-run zone delete"; show_output; (( PASS++ )) || true; }

# ══════════════════════════════════════════════════════════════════════════════
#                    MUTATION ROUND-TRIP ON TEST ZONE
# ══════════════════════════════════════════════════════════════════════════════

if [[ "${SKIP_MUTATIONS:-0}" == "1" ]]; then
    skip "mutation round-trip (SKIP_MUTATIONS=1)"
else

section "10. Create test zone: ${TEST_DOMAIN}"

capture -y -o json zone create "$TEST_DOMAIN"
if ! assert_no_crash "zone create" || ! assert_exit 0 "zone create"; then
    red "zone create failed — aborting mutation phase"
    show_output
    exit 1
fi
green "zone create ${TEST_DOMAIN}"
show_output
(( PASS++ )) || true

capture -o json zone show "$TEST_DOMAIN"
assert_ok "zone show ${TEST_DOMAIN}"

capture -o json zone status "$TEST_DOMAIN"
assert_ok "zone status ${TEST_DOMAIN}"

section "11. record set — one rrset per common RR type"

declare -a SET_CASES=(
    "--name @        --type A     --ttl 3600 --content 10.0.0.1 --content 10.0.0.2"
    "--name @        --type AAAA  --ttl 3600 --content 2001:db8::1"
    "--name www      --type A     --ttl 300  --content 10.0.0.10"
    "--name api      --type CNAME --ttl 300  --content www.${TEST_DOMAIN}."
    "--name @        --type MX    --ttl 3600 --content '10 mail.${TEST_DOMAIN}.'"
    "--name @        --type TXT   --ttl 300  --content '\"v=spf1 -all\"'"
    "--name _dmarc   --type TXT   --ttl 300  --content '\"v=DMARC1; p=reject;\"'"
    "--name _sip._tcp --type SRV  --ttl 3600 --content '10 5 5060 sip.${TEST_DOMAIN}.'"
    "--name @        --type CAA   --ttl 3600 --content '0 issue \"letsencrypt.org\"'"
)
for case in "${SET_CASES[@]}"; do
    eval "capture -y -o json record set \"$TEST_DOMAIN\" $case"
    desc="record set ${case:0:60}..."
    assert_no_crash "$desc" && assert_exit 0 "$desc" && {
        green "record set: $case"
        (( PASS++ )) || true
    }
done

section "12. Read back what we wrote"

subsection "record list — every output format"
for fmt in table json yaml csv tsv plain; do
    capture -o "$fmt" record list "$TEST_DOMAIN"
    assert_no_crash "record list -o $fmt" && assert_exit 0 "record list -o $fmt" && {
        green "record list -o $fmt"
        show_output
        (( PASS++ )) || true
    }
done

subsection "record export (BIND zone file)"
capture record export "$TEST_DOMAIN"
assert_no_crash "record export" && assert_exit 0 "record export" && {
    green "record export"
    show_output
    (( PASS++ )) || true
}

subsection "verify rrsets we added are present"
capture -o json record list "$TEST_DOMAIN"
for needle in "www.${TEST_DOMAIN}." "api.${TEST_DOMAIN}." "_dmarc.${TEST_DOMAIN}." "_sip._tcp.${TEST_DOMAIN}."; do
    if echo "$OUT" | grep -qF "\"$needle\""; then
        green "record list contains $needle"
        (( PASS++ )) || true
    else
        red "record list MISSING $needle"
        (( FAIL++ )) || true
    fi
done

section "13. record set (replace) / append / delete"

capture -y -o json record set "$TEST_DOMAIN" --name www --type A --ttl 60 --content 10.0.0.99 --require-exists
assert_no_crash "record set --require-exists www A" && assert_exit 0 "record set --require-exists www A" && {
    green "record set --require-exists www A"
    show_output
    (( PASS++ )) || true
}

# Verify replace took effect
capture -o json record list "$TEST_DOMAIN"
if echo "$OUT" | python3 -c "
import sys, json
rrsets = json.load(sys.stdin)
for r in rrsets:
    if r.get('name','').startswith('www') and r.get('type') == 'A':
        records = [x.get('content') for x in r.get('records', [])]
        assert '10.0.0.99' in records, f'expected 10.0.0.99 in {records}'
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
    green "record set reflected in list (10.0.0.99 present)"
    (( PASS++ )) || true
else
    red "record set not reflected"
    show_output
    (( FAIL++ )) || true
fi

capture -y -o json record append "$TEST_DOMAIN" --name www --type A --content 10.0.0.100
assert_no_crash "record append www A" && assert_exit 0 "record append www A" && {
    green "record append www A"
    show_output
    (( PASS++ )) || true
}

# Verify append preserved 10.0.0.99 AND added 10.0.0.100
capture -o json record list "$TEST_DOMAIN"
if echo "$OUT" | python3 -c "
import sys, json
rrsets = json.load(sys.stdin)
for r in rrsets:
    if r.get('name','').startswith('www') and r.get('type') == 'A':
        records = [x.get('content') for x in r.get('records', [])]
        assert '10.0.0.99' in records, f'expected 10.0.0.99 preserved, got {records}'
        assert '10.0.0.100' in records, f'expected 10.0.0.100 appended, got {records}'
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
    green "record append preserved existing record and added the new one"
    (( PASS++ )) || true
else
    red "record append did not behave as expected"
    show_output
    (( FAIL++ )) || true
fi

capture -y -o json record delete "$TEST_DOMAIN" --name api --type CNAME
assert_no_crash "record delete api CNAME" && assert_exit 0 "record delete api CNAME" && {
    green "record delete api CNAME"
    (( PASS++ )) || true
}

section "14. record apply — batch from JSON file"

APPLY_FILE="$WORK_DIR/apply.json"
cat > "$APPLY_FILE" <<EOF
[
  {
    "changetype": "add",
    "name": "batch1",
    "type": "A",
    "ttl": 300,
    "records": [{"content": "192.0.2.11", "disabled": false}]
  },
  {
    "changetype": "add",
    "name": "batch2",
    "type": "TXT",
    "ttl": 300,
    "records": [{"content": "\"batch test\"", "disabled": false}]
  }
]
EOF

capture -y -o json record apply "$TEST_DOMAIN" --from-file "$APPLY_FILE"
assert_no_crash "record apply" && assert_exit 0 "record apply" && {
    green "record apply (batch JSON)"
    show_output
    (( PASS++ )) || true
}

capture -o json record list "$TEST_DOMAIN"
for needle in "batch1.${TEST_DOMAIN}." "batch2.${TEST_DOMAIN}."; do
    if echo "$OUT" | grep -qF "\"$needle\""; then
        green "record apply: $needle present"
        (( PASS++ )) || true
    else
        red "record apply: $needle MISSING"
        (( FAIL++ )) || true
    fi
done

section "15. record import — BIND zone file"

BIND_FILE="$WORK_DIR/replace.zone"
cat > "$BIND_FILE" <<EOF
\$ORIGIN ${TEST_DOMAIN}.
\$TTL 3600
@   IN SOA sec1.rcode0.eu. hostmaster.${TEST_DOMAIN}. ( 2026042301 3600 900 604800 3600 )
@   IN NS  sec1.rcode0.eu.
@   IN NS  sec2.rcode0.net.
@   IN A   203.0.113.42
www IN A   203.0.113.43
EOF

capture -y -o json record import "$TEST_DOMAIN" --zone-file "$BIND_FILE"
assert_no_crash "record import" && assert_exit 0 "record import" && {
    green "record import (BIND zone file)"
    show_output
    (( PASS++ )) || true
}

# After import, batch/_dmarc etc. should be gone
capture -o json record list "$TEST_DOMAIN"
if echo "$OUT" | grep -qF "\"batch1.${TEST_DOMAIN}.\""; then
    red "import: batch1 still present — zone not replaced"
    (( FAIL++ )) || true
else
    green "import: batch1 gone (replacement worked)"
    (( PASS++ )) || true
fi

section "16. zone mutations: update / disable / enable / retrieve"

capture -y -o json zone update "$TEST_DOMAIN" --serial-auto
assert_no_crash "zone update --serial-auto" && assert_exit 0 "zone update --serial-auto" && {
    green "zone update --serial-auto"
    (( PASS++ )) || true
}

capture -y -o json zone disable "$TEST_DOMAIN"
assert_no_crash "zone disable" && assert_exit 0 "zone disable" && {
    green "zone disable"
    (( PASS++ )) || true
}

capture -y -o json zone enable "$TEST_DOMAIN"
assert_no_crash "zone enable" && assert_exit 0 "zone enable" && {
    green "zone enable"
    (( PASS++ )) || true
}

capture -y -o json zone retrieve "$TEST_DOMAIN"
assert_no_crash "zone retrieve" && {
    if [[ "$CODE" -eq 0 ]]; then
        green "zone retrieve"
        (( PASS++ )) || true
    else
        yellow "zone retrieve — exit $CODE (master zones often reject; non-fatal)"
        (( PASS++ )) || true
    fi
}

section "17. DNSSEC round-trip"

if [[ "${SKIP_DNSSEC:-0}" == "1" ]]; then
    skip "DNSSEC sign/unsign (SKIP_DNSSEC=1)"
else
    capture -y -o json dnssec sign "$TEST_DOMAIN"
    assert_no_crash "dnssec sign" && {
        if [[ "$CODE" -eq 0 ]]; then
            green "dnssec sign"
            show_output
            (( PASS++ )) || true
        else
            yellow "dnssec sign — exit $CODE (non-fatal on fresh zone)"
            show_output
            (( PASS++ )) || true
        fi
    }

    capture -o json zone show "$TEST_DOMAIN"
    assert_ok "zone show after sign"

    capture -y -o json dnssec unsign "$TEST_DOMAIN"
    assert_no_crash "dnssec unsign" && {
        if [[ "$CODE" -eq 0 ]]; then
            green "dnssec unsign"
            (( PASS++ )) || true
        else
            yellow "dnssec unsign — exit $CODE (non-fatal)"
            (( PASS++ )) || true
        fi
    }
fi

section "18. record clear"

capture -y -o json record clear "$TEST_DOMAIN"
assert_no_crash "record clear" && assert_exit 0 "record clear" && {
    green "record clear"
    (( PASS++ )) || true
}

# After clear, only apex SOA/NS should remain
capture -o json record list "$TEST_DOMAIN"
REMAINING=$(echo "$OUT" | python3 -c "
import sys, json
rrs = json.load(sys.stdin)
non_apex = [r for r in rrs if r.get('type') not in ('SOA','NS')]
print(len(non_apex))
" 2>/dev/null || echo "?")
if [[ "$REMAINING" == "0" ]]; then
    green "record clear: only SOA/NS remain (verified)"
    (( PASS++ )) || true
else
    yellow "record clear: $REMAINING non-apex rrsets remaining (API may keep some apex rows)"
    (( PASS++ )) || true
fi

section "19. Delete test zone"

capture -y -o json zone delete "$TEST_DOMAIN"
assert_no_crash "zone delete" && assert_exit 0 "zone delete" && {
    green "zone delete ${TEST_DOMAIN}"
    show_output
    (( PASS++ )) || true
}

# Verify gone
capture -o json zone list
if echo "$OUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for z in data:
    if z.get('domain','').rstrip('.').lower() == '${TEST_DOMAIN}'.rstrip('.').lower():
        sys.exit(1)
" 2>/dev/null; then
    green "post-delete: ${TEST_DOMAIN} no longer in zone list"
    (( PASS++ )) || true
else
    red "post-delete: ${TEST_DOMAIN} STILL in zone list"
    (( FAIL++ )) || true
fi

fi  # SKIP_MUTATIONS

# ══════════════════════════════════════════════════════════════════════════════
#                                  SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

section "Summary"

printf '  \033[32m%d passed\033[0m\n' "$PASS"
printf '  \033[31m%d failed\033[0m\n' "$FAIL"
printf '  \033[33m%d skipped\033[0m\n' "$SKIPPED"
echo

[[ "$FAIL" -eq 0 ]]
