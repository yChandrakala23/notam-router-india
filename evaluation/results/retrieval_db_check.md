# PostGIS retrieval check (generated)

ETD 2026-11-21T18:32:00+00:00

Geometry: {'with_geom': 726.0, 'valid': 726.0, 'srid_4326': 726.0, 'polygons': 726.0, 'min_area_ratio': 0.9922669708696887, 'max_area_ratio': 0.9943787061024985}

| Corridor | SQL | reference | agreement | edge cases (<=1% of corridor) | unexplained | median ms | max ms | by severity |
|---|---|---|---|---|---|---|---|---|
| DEL-BOM | 46 | 46 | 100.0% | 0 | 0 | 15.4 | 15.5 | {'BLOCKING': 0, 'RESTRICTIVE': 2, 'ADVISORY': 44} |
| DEL-BLR | 104 | 104 | 100.0% | 0 | 0 | 19.1 | 21.8 | {'BLOCKING': 0, 'RESTRICTIVE': 29, 'ADVISORY': 75} |
| BOM-MAA | 91 | 89 | 97.8% | 2 | 0 | 29.0 | 35.1 | {'BLOCKING': 0, 'RESTRICTIVE': 27, 'ADVISORY': 64} |
| CCU-DEL | 45 | 45 | 100.0% | 0 | 0 | 23.6 | 24.8 | {'BLOCKING': 0, 'RESTRICTIVE': 9, 'ADVISORY': 36} |
| DEL-SXR | 23 | 23 | 100.0% | 0 | 0 | 23.2 | 23.9 | {'BLOCKING': 0, 'RESTRICTIVE': 1, 'ADVISORY': 22} |