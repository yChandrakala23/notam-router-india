# Routing evaluation (generated)

Generated: 2026-11-21T18:55:50+00:00

Candidate graph: synthetic lateral-offset lattice (not real ATS airways) unless airway data is loaded.

## B. Designed conflict cases (SYNTHETIC NOTAMs, DEL-BOM)

Correct: 12/12; correct rejections 4/4; false rejections 0/8.

| Case | FL | Status | direct rejected | expected | correct | best extra NM | explanation |
|---|---|---|---|---|---|---|---|
| blocking area on direct route, inside FL band | 200 | OK | True | True / OK | True | 23.0 | Crosses SYN001 QRTCA near 23.8N 74.9E (r 40 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL000-250; route inside area from 267 to 347 NM at FL200-200, 05 06:35Z-05 06:46Z |
| same area, aircraft cruises above it | 350 | OK | False | False / OK | True | 0.0 | Clear of SYN002 QRTCA near 23.8N 74.9E (r 40 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL000-250: aircraft at FL350-350 is outside FL000-250 (route inside area from 267 to 347 NM at FL350-350, 05 06:35Z-05 06:46Z) |
| same area, NOTAM expired before ETD | 200 | OK | False | False / OK | True | 0.0 | Clear of SYN003 QRTCA near 23.8N 74.9E (r 40 NM), valid 2026-11-04T00:00:00Z to 2026-11-04T12:00:00Z, FL000-250: NOTAM not active while the aircraft is inside (route inside area from 267 to 347 NM at FL200-200, 05 06:35Z-05 06:46Z) |
| same area but RESTRICTIVE (warning only) | 200 | OK | False | False / OK | True | 0.0 | Passes through SYN004 QRTCA near 23.8N 74.9E (r 40 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL000-250; route inside area from 267 to 347 NM at FL200-200, 05 06:35Z-05 06:46Z |
| blocking area 300 NM off track | 200 | OK | False | False / OK | True | 0.0 | no conflict |
| low-level area (SFC-FL050) on track at cruise distance from airports | 350 | OK | False | False / OK | True | 0.0 | Clear of SYN006 QRTCA near 23.8N 74.9E (r 20 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL000-050: aircraft at FL350-350 is outside FL000-050 (route inside area from 287 to 327 NM at FL350-350, 05 06:38Z-05 06:43Z) |
| low-level area (SFC-FL050) on the climb-out 25% along track | 350 | OK | False | False / OK | True | 0.0 | Clear of SYN007 QRTCA near 26.2N 76.0E (r 10 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL000-050: aircraft at FL350-350 is outside FL000-050 (route inside area from 144 to 164 NM at FL350-350, 05 06:19Z-05 06:21Z) |
| low-level area (SFC-FL100) 10 NM after departure | 350 | NO_FEASIBLE_ROUTE | True | True / NO_FEASIBLE_ROUTE_OR_OK | True | None | Crosses SYN008 QRTCA near 28.4N 77.0E (r 5 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL000-100; route inside area from 6 to 14 NM at FL017-042, 05 06:00Z-05 06:01Z |
| destination aerodrome closed | 350 | AIRPORT_UNAVAILABLE | False | False / AIRPORT_UNAVAILABLE | True | 0.0 | arrival aerodrome VABB: SYN009 QRTCA near 19.1N 72.9E (r 5 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL000-999; in force at 05 07:21Z; no route choice avoids it |
| restricted area (Q-line circle) over the destination, all levels | 350 | NO_FEASIBLE_ROUTE | True | True / NO_FEASIBLE_ROUTE | True | None | Crosses SYN011 QRTCA near 19.1N 72.9E (r 15 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL000-999; route inside area from 601 to 615 NM at FL000-042, 05 07:20Z-05 07:21Z |
| en-route aerodrome closed (overflight at FL350) | 350 | OK | False | False / OK | True | 0.0 | Overflies VAAH: SYN012 QRTCA near 23.8N 74.9E (r 5 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL band unknown (no Q-line) concerns that aerodrome's own facilities and does not restrict overflight |
| wall across the corridor (r 250 NM), inside FL band | 200 | NO_FEASIBLE_ROUTE | True | True / NO_FEASIBLE_ROUTE | True | None | Crosses SYN010 QRTCA near 23.8N 74.9E (r 250 NM), valid 2026-11-05T00:00:00Z to 2026-11-06T00:00:00Z, FL000-300; route inside area from 58 to 557 NM at FL173-200, 05 06:07Z-05 07:14Z |