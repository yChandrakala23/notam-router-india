# ER Diagram

Mermaid source: `docs/person_a/er_diagram.mmd`. Rendered image: `docs/person_a/er_diagram.png`.

Paste the `.mmd` file into https://mermaid.live, or into any Markdown viewer that renders ` ```mermaid ` blocks.

Relationship summary:

- `data_source 1–N ingestion_run 1–N raw_notam 1–N notam_event`. An event points to its best raw observation.
- `notam_event 0..1–N notam_event` through `replaces_event_id` (NOTAMR/NOTAMC).
- `fir 1–N airport`, `fir 1–N notam_event`.
- Person B side: `airport 1–N route_request 1–N candidate_route 1–N route_conflict N–1 notam_event`, and `airway 1–N airway_edge N–1 waypoint`.

The full description is in `docs/person_a/dbms_report.md`.
