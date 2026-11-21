# Parser evaluation (generated)

Generated: 2026-11-21T18:31:49+00:00

## A. AAI monthly summaries (public, no Q-line)

- observations (PDF blocks): 1647
- unique raw records (content hash): 1135
- unique NOTAM identities: 1127
- parsed without error: 1134 (99.91%)
- failures: {'invalid end of validity: minute must be in 0..59': 1}
- aerodrome/FIR location assigned from section heading: 1065 (93.92%)

Independent check vs autorouter on 25 overlapping NOTAMs:

| field | correct / total | accuracy |
|---|---|---|
| estimated_end | 25 / 25 | 100.00% |
| location_A | 25 / 25 | 100.00% |
| notam_id | 25 / 25 | 100.00% |
| permanent | 25 / 25 | 100.00% |
| valid_from_B | 25 / 25 | 100.00% |
| valid_until_C | 25 / 25 | 100.00% |

Overall: {'correct': 150, 'total': 150, 'accuracy': 1.0}

## B. autorouter records (Q-line round trip)

Records: 143. rendered from structured JSON then parsed (round trip), see module docstring.

| field | correct / total | accuracy |
|---|---|---|
| action | 143 / 143 | 100.00% |
| centre_within_0.5_arcmin | 143 / 143 | 100.00% |
| fir | 143 / 143 | 100.00% |
| location_A | 143 / 143 | 100.00% |
| lower_fl | 143 / 143 | 100.00% |
| notam_id | 143 / 143 | 100.00% |
| parsed | 143 / 143 | 100.00% |
| purpose | 143 / 143 | 100.00% |
| q_code | 143 / 143 | 100.00% |
| radius_nm | 143 / 143 | 100.00% |
| scope | 143 / 143 | 100.00% |
| traffic | 143 / 143 | 100.00% |
| upper_fl | 143 / 143 | 100.00% |
| valid_from_B | 143 / 143 | 100.00% |
| valid_until_C | 143 / 143 | 100.00% |

Overall: {'correct': 2145, 'total': 2145, 'accuracy': 1.0}

Geometry: {'valid_polygon': {'correct': 143, 'total': 143, 'accuracy': 1.0}}

## C. Real ICAO-text fixtures (hand-checked)

Overall: {'correct': 30, 'total': 30, 'accuracy': 1.0}

## Totals

Real NOTAM records exercised: 1281