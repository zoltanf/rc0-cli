# API Coverage

Generated from pinned OpenAPI spec v2.9.

| Status | Method | Endpoint | CLI Command | Notes |
|--------|--------|----------|-------------|-------|
| ✅ | `GET` | `/api/v1/acme/zones/{zone}/rrsets` | `rc0 acme list-challenges` |  |
| ✅ | `PATCH` | `/api/v1/acme/zones/{zone}/rrsets` | `rc0 acme add-challenge / remove-challenge` |  |
| ✅ | `GET` | `/api/v1/acme/{zone}` | `rc0 acme zone-exists` |  |
| ✅ | `GET` | `/api/v2/messages` | `rc0 messages poll` |  |
| ✅ | `GET` | `/api/v2/messages/list` | `rc0 messages list` |  |
| ✅ | `DELETE` | `/api/v2/messages/{id}` | `rc0 messages ack` |  |
| ✅ | `GET` | `/api/v2/reports/accounting` | `rc0 report accounting` |  |
| ✅ | `GET` | `/api/v2/reports/domainlist` | `rc0 report domainlist` |  |
| ✅ | `GET` | `/api/v2/reports/nxdomains` | `rc0 report nxdomains` |  |
| ✅ | `GET` | `/api/v2/reports/problematiczones` | `rc0 report problematic-zones` |  |
| ✅ | `GET` | `/api/v2/reports/queryrates` | `rc0 report queryrates` |  |
| ✅ | `GET` | `/api/v2/settings` | `rc0 settings show` |  |
| ✅ | `PUT` | `/api/v2/settings/secondaries` | `rc0 settings secondaries set` |  |
| ✅ | `DELETE` | `/api/v2/settings/secondaries` | `rc0 settings secondaries unset` |  |
| ✅ | `PUT` | `/api/v2/settings/tsig/in` | `rc0 settings tsig-in set` |  |
| ✅ | `DELETE` | `/api/v2/settings/tsig/in` | `rc0 settings tsig-in unset` |  |
| ✅ | `PUT` | `/api/v2/settings/tsig/out` | `rc0 settings tsig-out set` |  |
| ✅ | `DELETE` | `/api/v2/settings/tsig/out` | `rc0 settings tsig-out unset` |  |
| ⚠️ | `PUT` | `/api/v2/settings/tsigout` | `[DEPRECATED — no CLI command]` | [DEPRECATED] |
| ⚠️ | `DELETE` | `/api/v2/settings/tsigout` | `[DEPRECATED — no CLI command]` | [DEPRECATED] |
| ✅ | `GET` | `/api/v2/stats/countries` | `rc0 stats countries` |  |
| ✅ | `GET` | `/api/v2/stats/querycounts` | `rc0 stats queries` |  |
| ✅ | `GET` | `/api/v2/stats/topmagnitude` | `rc0 stats topmagnitude` | [DEPRECATED] |
| ✅ | `GET` | `/api/v2/stats/topnxdomains` | `rc0 stats topnxdomains` | [DEPRECATED] |
| ✅ | `GET` | `/api/v2/stats/topqnames` | `rc0 stats topqnames` | [DEPRECATED] |
| ✅ | `GET` | `/api/v2/stats/topzones` | `rc0 stats topzones` |  |
| ✅ | `GET` | `/api/v2/tsig` | `rc0 tsig list` |  |
| ✅ | `POST` | `/api/v2/tsig` | `rc0 tsig add` |  |
| ✅ | `GET` | `/api/v2/tsig/out` | `rc0 tsig list-out` | [DEPRECATED] |
| ⚠️ | `POST` | `/api/v2/tsig/out` | `[DEPRECATED — no CLI command]` | [DEPRECATED] |
| ⚠️ | `PUT` | `/api/v2/tsig/out/{keyname}` | `[DEPRECATED — no CLI command]` | [DEPRECATED] |
| ⚠️ | `DELETE` | `/api/v2/tsig/out/{keyname}` | `[DEPRECATED — no CLI command]` | [DEPRECATED] |
| ✅ | `GET` | `/api/v2/tsig/{keyname}` | `rc0 tsig show` |  |
| ✅ | `PUT` | `/api/v2/tsig/{keyname}` | `rc0 tsig update` |  |
| ✅ | `DELETE` | `/api/v2/tsig/{keyname}` | `rc0 tsig delete` |  |
| ✅ | `GET` | `/api/v2/zones` | `rc0 zone list` |  |
| ✅ | `POST` | `/api/v2/zones` | `rc0 zone create` |  |
| ✅ | `GET` | `/api/v2/zones/{zone}` | `rc0 zone show` |  |
| ✅ | `PUT` | `/api/v2/zones/{zone}` | `rc0 zone update` |  |
| ✅ | `PATCH` | `/api/v2/zones/{zone}` | `rc0 zone enable / disable` |  |
| ✅ | `DELETE` | `/api/v2/zones/{zone}` | `rc0 zone delete` |  |
| ✅ | `POST` | `/api/v2/zones/{zone}/dsupdate` | `rc0 dnssec ack-ds` |  |
| ✅ | `GET` | `/api/v2/zones/{zone}/inbound` | `rc0 zone xfr-in show` |  |
| ✅ | `POST` | `/api/v2/zones/{zone}/inbound` | `rc0 zone xfr-in set` |  |
| ✅ | `DELETE` | `/api/v2/zones/{zone}/inbound` | `rc0 zone xfr-in unset` |  |
| ✅ | `POST` | `/api/v2/zones/{zone}/keyrollover` | `rc0 dnssec keyrollover` |  |
| ✅ | `GET` | `/api/v2/zones/{zone}/outbound` | `rc0 zone xfr-out show` |  |
| ✅ | `POST` | `/api/v2/zones/{zone}/outbound` | `rc0 zone xfr-out set` |  |
| ✅ | `DELETE` | `/api/v2/zones/{zone}/outbound` | `rc0 zone xfr-out unset` |  |
| ✅ | `POST` | `/api/v2/zones/{zone}/retrieve` | `rc0 zone retrieve` |  |
| ✅ | `GET` | `/api/v2/zones/{zone}/rrsets` | `rc0 record list` |  |
| ✅ | `PUT` | `/api/v2/zones/{zone}/rrsets` | `rc0 record replace-all` |  |
| ✅ | `PATCH` | `/api/v2/zones/{zone}/rrsets` | `rc0 record add / update / delete / apply` |  |
| ✅ | `DELETE` | `/api/v2/zones/{zone}/rrsets` | `rc0 record clear` |  |
| ✅ | `POST` | `/api/v2/zones/{zone}/sign` | `rc0 dnssec sign` |  |
| ✅ | `POST` | `/api/v2/zones/{zone}/simulate/dsremoved` | `rc0 dnssec simulate dsremoved` |  |
| ✅ | `POST` | `/api/v2/zones/{zone}/simulate/dsseen` | `rc0 dnssec simulate dsseen` |  |
| ✅ | `GET` | `/api/v2/zones/{zone}/stats/magnitude` | `rc0 stats zone magnitude` | [DEPRECATED] |
| ✅ | `GET` | `/api/v2/zones/{zone}/stats/nxdomains` | `rc0 stats zone nxdomains` | [DEPRECATED] |
| ✅ | `GET` | `/api/v2/zones/{zone}/stats/qnames` | `rc0 stats zone qnames` | [DEPRECATED] |
| ✅ | `GET` | `/api/v2/zones/{zone}/stats/queries` | `rc0 stats zone queries` |  |
| ✅ | `GET` | `/api/v2/zones/{zone}/status` | `rc0 zone status` |  |
| ✅ | `POST` | `/api/v2/zones/{zone}/unsign` | `rc0 dnssec unsign` |  |
