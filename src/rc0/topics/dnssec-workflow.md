# DNSSEC workflow

`rc0 dnssec` manages DNSSEC signing for zones on the RcodeZero platform.
DNSSEC adds cryptographic signatures to DNS records so resolvers can verify
that responses are authentic and have not been tampered with in transit.

RcodeZero manages the actual keys (KSK and ZSK) on your behalf. Your
responsibilities are to trigger signing, acknowledge DS record changes at
your registrar, and initiate key rollovers when needed.

## Signing a zone

```
rc0 dnssec sign example.com
```

This starts DNSSEC signing. The provider generates a KSK and ZSK, signs
the zone, and publishes the DS record. No confirmation prompt — signing is
not destructive.

**Optional flags:**

- `--ignore-safety-period` — bypass the TTL safety period check. Useful
  when you need to sign immediately and accept the risk that resolvers with
  cached unsigned responses may briefly reject signed answers.
- `--enable-cds-cdnskey` — publish CDS and CDNSKEY records alongside the
  DS record. Required for automated DS delegation with some registrars.

Use `--dry-run` to preview the request without making a change:

```
rc0 dnssec sign example.com --dry-run -o json
```

## Acknowledging DS records

After signing, the provider sends a `DSUPDATE` notification to your message
queue. Once you have updated the DS record at your registrar, acknowledge
the update:

```
rc0 dnssec ack-ds example.com
```

This clears all `DSUPDATE` messages for the zone from the queue. You can
inspect pending messages first:

```
rc0 messages list
```

## KSK rollover lifecycle

A key rollover replaces the KSK with a new one without any signing gap.
The full sequence is:

```
# 1. Initiate rollover — generates a new KSK and publishes it alongside the old one
rc0 dnssec keyrollover example.com

# 2. Wait for the provider to publish a DSSEEN or DSUPDATE message confirming
#    the new DS record is visible in the parent zone.
rc0 messages list

# 3. Acknowledge — removes the old KSK and clears the notifications
rc0 dnssec ack-ds example.com
```

`keyrollover` prompts for confirmation (`y/N`). Pass `-y` to skip in scripts.

## Unsigning a zone

Removing DNSSEC is irreversible without re-signing and requires that DS
records are removed at the registrar first. To prevent accidents, `unsign`
requires the `--force` flag and then prompts for confirmation:

```
rc0 dnssec unsign example.com --force
```

**Warning:** If DS records remain at the registrar after unsigning, DNSSEC-
validating resolvers will treat the zone as broken and return SERVFAIL.
Remove the DS records at your registrar *before* or immediately after
running this command.

Pass `-y` to skip the confirmation prompt in scripts:

```
rc0 dnssec unsign example.com --force -y
```

## Test-environment simulation

The `simulate` sub-group is only available on non-production API instances.
It pushes synthetic DNSSEC events into the message queue, letting you test
rollover and unsign workflows without waiting for real DNS propagation.

```
# Point at the test environment
rc0 --api-url https://my-test.rcodezero.at dnssec simulate dsseen example.com
rc0 --api-url https://my-test.rcodezero.at dnssec simulate dsremoved example.com
```

- `dsseen` — simulates the provider observing DS records in the parent zone
  (triggers the rollover continuation path).
- `dsremoved` — simulates DS records disappearing from the parent zone
  (used to test the unsign flow).

Running either command against the production API (`https://my.rcodezero.at`)
is blocked with an error.

## Monitoring

Watch the message queue for DNSSEC events during signing and rollover:

```
rc0 messages list
```

Relevant message types: `DSUPDATE` (new DS record published), `DSSEEN`
(DS confirmed visible in parent), `DSREMOVED` (DS removed from parent).
Acknowledge messages that require action with `rc0 messages ack <id>` or
clear all with `rc0 messages ack-all`.
