# Annotation audit — data/labelled/aai_label_sheet.csv (generated)

Generated: 2026-11-21T18:28:45+00:00

Labels are **preliminary**: nothing below changes a label. Review flags are heuristics that compare the label with the severity definitions in `classification/rules.py`; each flag states its reason.

- rows in sheet: 300
- rows with at least one human label: 300
- unique NOTAM identities with labels: 300
- usable for category / severity / both: 300 / 300 / 300
- issues by level: {'review': 429}
- category distribution: {'AERODROME': 121, 'RUNWAY': 41, 'OBSTACLE': 23, 'NAVAID_COMMS': 22, 'NAV_WARNING': 73, 'PROCEDURE': 20}
- severity distribution: {'RESTRICTIVE': 176, 'ADVISORY': 107, 'BLOCKING': 17}

## Errors (excluded from training/evaluation)

Unannotated rows: 0

None.

## BLOCKING annotations (each needs explicit confirmation)

### row 4 — VOMM A1730/26 (VOMM)

- label: NAVAID_COMMS / **BLOCKING**; predicted NAV_WARNING / BLOCKING
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: launch_firing
- E-text: REF VOMF NOTAM A1726/26 REG ROCKET LAUNCH FM SHAR RANGE. DRG ACT, THE FLW SID NOT AVBL: RWY07 KAMGU 2A RWY25 KAMGU 2B RWY12 KAMGU 2C RWY30 KAMGU 2D DEPARTURES MAY EXP TACTICAL RADAR VECTORING CLR OF THE ACT

Needs review because:
- BLOCKING for category NAVAID_COMMS; rules.py gives these at most RESTRICTIVE

### row 23 — VIDP A1418/26 (VABF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_use_plan, vertical_limits
- E-text: AIRSPACE USE PLAN (AUP) TSA/TRA /AMC-MANAGEABLE AIRSPACE ACT AS FLW : NR AIRSPACE ID TIME FM TIME TO LOWER FL UPPER FL 1 TRA503(A) [PUNE] 0130 1200 FL325 FL460 2 TRA503(A) [PUNE] 1330 1730 FL325 FL460 3 TRA503(B) [PUNE] 0130 1200 FL325 FL460 4 TRA503(B) [PUNE] 1330 1730 FL325 FL460 5 TRA509A 0000 2359 SFC FL270 6 TRA509B 0230 0730 FL270 UNL 7 TRA509B 1000 1100 FL270 UNL 8 TRA509B 1430 1630 FL270 U

Needs review because:
- BLOCKING for an Airspace Use Plan: it lists many TRA/TSA activations and conditional routes, each with its own times and FL band; whether a route is blocked depends on which area it crosses, so a single BLOCKING label over-generalises
- no lateral limits in the E-text and AAI summaries carry no Q-line circle: routing can apply this only at aerodrome / FIR level

### row 43 — VIDP A0933/26 (VECF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_not_available, lateral_limits, navaid_us
- E-text: MAY 04-07 11-14 18-21 25-26 28 0330-0630 1400-1625, MAY 08 15 22 29 0330-0630 AIRSPACE BOUNDED WI COORD (EX-ROMEO): 273705N0780907E - 265812N0795114E - 264038N0800214E - 250612N0791341E - 250920N0772625E - 262242N0772304E - 263754N0775411E - 264208N0781515E - 273705N0780907E NOT AVBL DUE AIR EXER (EXCLUDING DANGER AREA FALLING WI EXER AREA). DRG EXER PERIOD FLW RESTRICTIONS APPLY: 1.ATS RTE L759 B

No automatic concern found. Still unverified: confirm that the activity makes the airspace/aerodrome unusable while active (not merely restricted).

### row 64 — VOMM A1459/26 (VOMF)

- label: NAV_WARNING / **BLOCKING**; predicted PROCEDURE / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_use_plan, vertical_limits
- E-text: AIRSPACE USE PLAN (AUP) TSA/TRA/AMC-MANAGEABLE AIRSPACE ACT AS FLW : NR AIRSPACE ID TIME FM TIME TO LOWER FL UPPER FL 1 TRA503(A) [PUNE] 0130 1200 FL325 FL460 2 TRA503(B) [PUNE] 0130 1200 FL325 FL460 3 TRA601(A) [PANAGARH] 0049 1124 GND 4000FT AMSL 4 TRA601(B) [PANAGARH] 0049 1124 GND FL105 5 TRA601(C) [PANAGARH] 0049 1124 GND FL105 6 TRA604 [TEZPUR] 0230 1130 FL130 FL380 7 TRA604 [TEZPUR] 1200 18

Needs review because:
- BLOCKING for an Airspace Use Plan: it lists many TRA/TSA activations and conditional routes, each with its own times and FL band; whether a route is blocked depends on which area it crosses, so a single BLOCKING label over-generalises
- no lateral limits in the E-text and AAI summaries carry no Q-line circle: routing can apply this only at aerodrome / FIR level

### row 95 — VIDP A0713/26 (VECF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_not_available, lateral_limits, navaid_us
- E-text: AIRSPACE BOUNDED WI COORD (EX-ROMEO): 273705N0780907E - 265812N0795114E - 264038N0800214E - 250612N0791341E - 250920N0772625E - 262242N0772304E - 263754N0775411E - 264208N0781515E - 273705N0780907E (EXCLUDING DANGER AREA FALLING WI EXER AREA) NOT AVBL DUE AIR EXER. DRG EXER PERIOD FLW RESTRICTIONS APPLY: 1. ATS RTE L759 BTN DELHI VOR (DPN) AND KHAJURAHO VOR (KKJ) NOT AVBL. ALTN RTE AVBL: DPN DCT A

No automatic concern found. Still unverified: confirm that the activity makes the airspace/aerodrome unusable while active (not merely restricted).

### row 99 — VIDP A1162/26 (VIDF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_not_available, lateral_limits, vertical_limits
- E-text: AIRSPACE BOUNDED WI COORD(B1): 3348N07524E- 3402N07716E - 3303N07716E- 3134N07716E-3114N07632E-3114N07616E- 3117N07545E - 3143N07542E - 3348N07524E NOT AVBL FM FL150 TO FL500 DUE AIR EXER. AIR EXER CORRIDOR OF AIRSPACE (B2) BOUNDED WI COORD: 3303N07716E - 3303N07757E - 3135N07807E - 3134N07716E - 3303N07716E NOT AVBL FM FL240 TO FL320 DUE AIR EXER. AIR EXER CORRIDOR OF AIRSPACE (B3) BOUNDED WI COO

No automatic concern found. Still unverified: confirm that the activity makes the airspace/aerodrome unusable while active (not merely restricted).

### row 119 — VIDP A1101/26 (VECF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_not_available, lateral_limits, navaid_us
- E-text: AIRSPACE BOUNDED WI COORD (EX-ROMEO): 273705N0780907E - 265812N0795114E - 264038N0800214E - 250612N0791341E - 250920N0772625E - 262242N0772304E - 263754N0775411E - 264208N0781515E - 273705N0780907E NOT AVBL DUE AIR EXER (EXCLUDING DANGER AREA FALLING WI EXER AREA). DRG EXER PERIOD FLW RESTRICTIONS APPLY: 1.ATS RTE L759 BTN DELHI VOR (DPN) AND KHAJURAHO VOR (KKJ) NOT AVBL. ALTN RTE AVBL: DPN DCT AL

No automatic concern found. Still unverified: confirm that the activity makes the airspace/aerodrome unusable while active (not merely restricted).

### row 128 — VOMM A1701/26 (VOMF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: lateral_limits, launch_firing, vertical_limits
- E-text: FLD FRNG RANGE ACT AREA OF OPS: 5NM AROUND COORD 104010N0782500E FROM : GND TO : 1500FT AMSL

No automatic concern found. Still unverified: confirm that the activity makes the airspace/aerodrome unusable while active (not merely restricted).

### row 151 — VIDP A1358/26 (VECF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_not_available, lateral_limits, navaid_us
- E-text: AIRSPACE BOUNDED WI COORD (EX-ROMEO): 273705N0780907E - 265812N0795114E - 264038N0800214E - 250612N0791341E - 250920N0772625E - 262242N0772304E - 263754N0775411E - 264208N0781515E - 273705N0780907E NOT AVBL DUE AIR EXER (EXCLUDING DANGER AREA FALLING WI EXER AREA). DRG EXER PERIOD FLW RESTRICTIONS APPLY: 1.ATS RTE L759 BTN DELHI VOR (DPN) AND KHAJURAHO VOR (KKJ) NOT AVBL. ALTN RTE AVBL: DPN DCT AL

No automatic concern found. Still unverified: confirm that the activity makes the airspace/aerodrome unusable while active (not merely restricted).

### row 212 — VOMM A2923/26 (VOMF)

- label: NAV_WARNING / **BLOCKING**; predicted NAV_WARNING / BLOCKING
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_not_available, designated_area, launch_firing, navaid_us, no_flight, vertical_limits
- E-text: VOD175(A) THUMBA-1 ROCKET FRNG RANGE ACT. 1.LAUNCH WILL TAKE PLACE BTN 0530Z AND 0700Z. ACTUAL LAUNCH WINDOW IS EXP TO BE 15 MIN. 2.ARR/DEP AT THIRUVANANTHAPURAM AP MAY BE DLA DRG RANGE ACT. ARRIVALS MAY BE REQUIRED BY ATC TO HOLD CLR OF DNG AREA. DEPARTURES MAY BE DLA ON GND. MAX ANTICIPATED DLA FOR ARR AND DEP IS AROUND 30 MIN. 3.RNAV SIDS & STARS FOR THIRUVANANTHAPURAM AP SHALL NOT BE AVBL DRG 

Needs review because:
- no lateral limits in the E-text and AAI summaries carry no Q-line circle: routing can apply this only at aerodrome / FIR level

### row 218 — VECC A0765/26 (VECF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: lateral_limits, vertical_limits
- E-text: AIR EXER INPR WI AREA BOUNDED BY COORD: POINT A-275530.6N 0970236.5E POINT B-264651.7N 0950003.7E POINT C-250842.7N 0941528.8E POINT D-252121.2N 0924655.1E POINT E-254625.0N 0921728.4E POINT F-262620.7N 0921523.8E POINT G-263126.1N 0893347.3E POINT H-263838.0N 0893319.4E POINT I-264229.9N 0920337.2E POINT J-264444.1N 0920819.7E POINT K-272409.1N 0922541.3E POINT L-285414.0N 0943959.5 E AND POINT A

Needs review because:
- BLOCKING NAV_WARNING without firing/launch/no-flight/airspace-not-available wording; rules.py blocks only WM/WD/WW/WR-type hazards and active R* areas

### row 251 — VIDP A0718/26 (VABF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_not_available, lateral_limits, navaid_us, vertical_limits
- E-text: AIRSPACE BOUNDED WI COORD(A3): 2735N07737E - 2735N07809E - 2730N07829E - 2712N07917E - 2651N08003E - 2645N08008E - 2548N08119E - 2530N08200E - 2508N08014E - 2514N08008E - 2513N07939E - 2504N07929E - 2424N07834E - 2424N07811E - 2447N077 29E - 2503N07729E - 2735N07737E NOT AVBL DUE AIR EXER. AIRSPACE BOUNDED WI COORD(A4): 2513N07940E - 2514N08008E - 2508N08015E - 2530N08200E - 2431N08200E- 2425N0815

No automatic concern found. Still unverified: confirm that the activity makes the airspace/aerodrome unusable while active (not merely restricted).

### row 259 — VIDP A0738/26 (VABF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_use_plan, vertical_limits
- E-text: AIRSPACE USE PLAN (AUP) TSA/TRA /AMC-MANAGEABLE AIRSPACE ACT AS FLW : NR AIRSPACE ID TIME FM TIME TO LOWER FL UPPER FL 1 TRA503(A) [PUNE] 0130 1200 FL325 FL460 2 TRA503(B) [PUNE] 0130 1200 FL325 FL460 3 TRA506(A) [JAMNAGAR] 0330 0830 FL325 FL360 4 TRA506(B) [JAMNAGAR] 0330 0830 FL325 FL360 5 TSA701 (A) [ADAMPUR] 0000 2359 FL145 FL280 6 TSA701 (B) [ADAMPUR] 0000 2359 GND FL280 7 TRA702 (A) [SRINAGA

Needs review because:
- BLOCKING for an Airspace Use Plan: it lists many TRA/TSA activations and conditional routes, each with its own times and FL band; whether a route is blocked depends on which area it crosses, so a single BLOCKING label over-generalises
- no lateral limits in the E-text and AAI summaries carry no Q-line circle: routing can apply this only at aerodrome / FIR level

### row 271 — VIDP A0714/26 (VECF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_not_available, lateral_limits, navaid_us
- E-text: AIRSPACE BOUNDED WI COORD (EX-ROMEO): 273705N0780907E - 265812N0795114E - 264038N0800214E - 250612N0791341E - 250920N0772625E - 262242N0772304E - 263754N0775411E - 264208N0781515E - 273705N0780907E (EXCLUDING DANGER AREA FALLING WI EXER AREA) NOT AVBL DUE AIR EXER. DRG EXER PERIOD FLW RESTRICTIONS APPLY: 1. ATS RTE L759 BTN DELHI VOR (DPN) AND KHAJURAHO VOR (KKJ) NOT AVBL. ALTN RTE AVBL: DPN DCT A

No automatic concern found. Still unverified: confirm that the activity makes the airspace/aerodrome unusable while active (not merely restricted).

### row 272 — VOMM A2617/26 (VOMF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: designated_area, launch_firing, vertical_limits
- E-text: VOD-188 CHENGALPATTU FRNG RANGE ACT FROM : GND TO : 5000FT AGL

Needs review because:
- no lateral limits in the E-text and AAI summaries carry no Q-line circle: routing can apply this only at aerodrome / FIR level

### row 294 — VECC A1003/26 (VECF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: lateral_limits, vertical_limits
- E-text: AIR EXER INPR WI AREA BOUNDED BY COORD: POINT A- 275530.6N 0970236.5E POINT B- 264651.7N 0950003.7E POINT C- 250842.7N 0941528.8E POINT D- 252121.2N 0924655.1E POINT E- 254625.0N 0921523.8E POINT G- 263126.1N 0893347.3E POINT H- 263838.0N 0893319.4E POINT I- 264229.9N 0920337.2E POINT J- 264444.1N 0920819.7E POINT K- 272409.1N 0922541.3E POINT L- 285414.0N 0943959.5E AND POINT A-275530.6N 0970236.

Needs review because:
- BLOCKING NAV_WARNING without firing/launch/no-flight/airspace-not-available wording; rules.py blocks only WM/WD/WW/WR-type hazards and active R* areas

### row 299 — VIDP A1100/26 (VECF)

- label: NAV_WARNING / **BLOCKING**; predicted AERODROME / ADVISORY
- note: Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.
- text cues found: airspace_not_available, lateral_limits, navaid_us
- E-text: AIRSPACE BOUNDED WI COORD (EX-ROMEO): 273705N0780907E - 265812N0795114E - 264038N0800214E - 250612N0791341E - 250920N0772625E - 262242N0772304E - 263754N0775411E - 264208N0781515E - 273705N0780907E NOT AVBL DUE AIR EXER (EXCLUDING DANGER AREA FALLING WI EXER AREA). DRG EXER PERIOD FLW RESTRICTIONS APPLY: 1.ATS RTE W33 NOT AVBL. ALTN RTE AVBL FOR CIVIL SKED FLIGHT OPERATING BTN DELHI AND KKJ. FOR E

No automatic concern found. Still unverified: confirm that the activity makes the airspace/aerodrome unusable while active (not merely restricted).

## Other questionable severity assignments

| row | NOTAM | reason |
|---|---|---|
| 15 | VIDP A0567/26 | RESTRICTIVE but the text says the aerodrome is closed; rules.py maps aerodrome closure (FA..LC) to BLOCKING |
| 26 | VECC A0989/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 26 | VECC A0989/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 45 | VABB A0804/26 | ADVISORY but the text describes firing/launch or a no-flight zone; rules.py treats active hazards of this kind as BLOCKING (WM/R*) or at least RESTRICTIVE |
| 45 | VABB A0804/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 54 | VECC A0798/26 | ADVISORY but the text describes firing/launch or a no-flight zone; rules.py treats active hazards of this kind as BLOCKING (WM/R*) or at least RESTRICTIVE |
| 54 | VECC A0798/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 54 | VECC A0798/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 74 | VECC A0803/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 74 | VECC A0803/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 86 | VECC A0607/26 | ADVISORY but the text describes firing/launch or a no-flight zone; rules.py treats active hazards of this kind as BLOCKING (WM/R*) or at least RESTRICTIVE |
| 86 | VECC A0607/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 91 | VIDP A1320/26 | ADVISORY but the text describes firing/launch or a no-flight zone; rules.py treats active hazards of this kind as BLOCKING (WM/R*) or at least RESTRICTIVE |
| 91 | VIDP A1320/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 91 | VIDP A1320/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 106 | VECC A0612/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 106 | VECC A0612/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 142 | VECC A0500/26 | RESTRICTIVE but the text says the aerodrome is closed; rules.py maps aerodrome closure (FA..LC) to BLOCKING |
| 162 | VECC A1030/26 | ADVISORY but the text describes firing/launch or a no-flight zone; rules.py treats active hazards of this kind as BLOCKING (WM/R*) or at least RESTRICTIVE |
| 162 | VECC A1030/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 162 | VECC A1030/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 174 | VECC A1033/26 | ADVISORY but the text describes firing/launch or a no-flight zone; rules.py treats active hazards of this kind as BLOCKING (WM/R*) or at least RESTRICTIVE |
| 174 | VECC A1033/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 177 | VABB A0599/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 177 | VABB A0599/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 198 | VECC A0988/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 198 | VECC A0988/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 234 | VECC A0360/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 234 | VECC A0360/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 261 | VABB A0303/26 | ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); rules.py maps active R* areas to BLOCKING |
| 261 | VABB A0303/26 | category AERODROME for an airspace activity (firing / danger area / no-overfly); by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*) |
| 267 | VIDP A0566/26 | RESTRICTIVE but the text says the aerodrome is closed; rules.py maps aerodrome closure (FA..LC) to BLOCKING |

## Conflicts across identical texts

None.

## Generic notes on disputed rows

| row | NOTAM | field | detail |
|---|---|---|---|
| 1 | VABB A0462/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 2 | VECC A0241/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 4 | VOMM A1730/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 5 | VABB A0707/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 12 | VOMM A2740/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 13 | VABB A0164/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 15 | VIDP A0567/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 16 | VOMM A1041/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 19 | VIDP A0112/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 20 | VOMM A0638/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 22 | VECC A1045/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 23 | VIDP A1418/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 25 | VABB A0714/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 27 | VIDP A1235/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 28 | VOMM A2671/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 32 | VOMM A0460/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 34 | VECC A0558/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 35 | VIDP A1120/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 36 | VOMM A2969/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 40 | VOMM A1176/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 43 | VIDP A0933/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 46 | VECC A0415/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 49 | VABB A0471/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 52 | VOMM A2605/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 53 | VABB A0632/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 55 | VIDP A0978/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 58 | VECC A0811/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 59 | VIDP A0681/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 61 | VABB A0175/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 63 | VIDP A1108/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 64 | VOMM A1459/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 66 | VECC A0575/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 67 | VIDP A1019/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 78 | VECC A0747/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 81 | VABB A0791/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 82 | VECC A0808/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 84 | VOMM A1285/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 87 | VIDP A0847/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 89 | VABB A0671/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 90 | VECC A1020/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 92 | VOMM A2888/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 93 | VABB A0492/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 94 | VECC A0823/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 95 | VIDP A0713/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 96 | VOMM A1142/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 99 | VIDP A1162/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 100 | VOMM A1234/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 103 | VIDP A0371/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 104 | VOMM A0983/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 105 | VABB A0219/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 107 | VIDP A0430/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 108 | VOMM A0385/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 109 | VABB A0524/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 110 | VECC A0583/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 111 | VIDP A0846/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 113 | VABB A0815/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 118 | VECC A0966/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 119 | VIDP A1101/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 120 | VOMM A0389/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 121 | VABB A0506/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 123 | VIDP A1233/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 125 | VABB A0307/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 126 | VECC A0149/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 127 | VIDP A1092/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 128 | VOMM A1701/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 131 | VIDP A0043/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 133 | VABB A0558/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 134 | VECC A1026/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 135 | VIDP A0900/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 137 | VABB A0744/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 140 | VOMM A1187/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 142 | VECC A0500/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 144 | VOMM A1184/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 146 | VECC A0601/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 147 | VIDP A0740/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 148 | VOMM A2966/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 150 | VECC A0484/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 151 | VIDP A1358/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 152 | VOMM A1689/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 154 | VECC A0716/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 155 | VIDP A0014/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 156 | VOMM A2500/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 157 | VABB A0177/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 166 | VECC A0733/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 167 | VIDP A1295/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 168 | VOMM A0048/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 170 | VECC A0337/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 171 | VIDP A0505/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 176 | VOMM A2342/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 179 | VIDP A0446/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 180 | VOMM A1386/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 181 | VABB A0461/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 182 | VECC A0554/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 183 | VIDP A1068/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 184 | VOMM A1651/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 187 | VIDP A0814/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 188 | VOMM A1593/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 189 | VABB A0178/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 190 | VECC A1019/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 191 | VIDP A1435/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 192 | VOMM A1469/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 194 | VECC A0443/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 195 | VIDP A1104/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 196 | VOMM A2451/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 200 | VOMM A0578/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 203 | VIDP A1190/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 206 | VECC A0968/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 210 | VECC A1039/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 214 | VECC A0621/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 216 | VOMM A1353/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 217 | VABB A0326/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 218 | VECC A0765/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 226 | VECC A0599/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 227 | VIDP A0463/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 228 | VOMM A1054/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 229 | VABB A0518/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 236 | VOMM A2387/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 238 | VECC A0490/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 239 | VIDP A1607/21 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 241 | VABB A0654/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 242 | VECC A0967/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 243 | VIDP A0595/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 244 | VOMM A2948/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 246 | VECC A0423/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 247 | VIDP A0964/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 249 | VABB A0787/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 250 | VECC A0732/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 251 | VIDP A0718/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 253 | VABB A0761/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 254 | VECC A0036/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 255 | VIDP A1015/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 257 | VABB A0679/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 259 | VIDP A0738/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 260 | VOMM A2850/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 262 | VECC A0317/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 263 | VIDP A1105/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 264 | VOMM A1381/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 266 | VECC A1014/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 267 | VIDP A0566/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 270 | VECC A0881/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 271 | VIDP A0714/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 272 | VOMM A2617/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 273 | VABB A0028/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 274 | VECC A0731/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 275 | VIDP A1424/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 276 | VOMM A0629/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 278 | VECC A1027/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 279 | VIDP A0958/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 280 | VOMM A2644/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 281 | VABB A0557/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 284 | VOMM A1320/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 285 | VABB A0793/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 287 | VIDP A1165/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 288 | VOMM A2843/26 | notes | label differs from prediction but the note is generic/uninformative ('Review operational impact; facility/service unavailability may affect route or airport operations differently.'); record the reason for the decision |
| 291 | VIDP A0965/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 292 | VOMM A1666/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 294 | VECC A1003/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 297 | VABB A0044/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |
| 298 | VECC A0835/26 | notes | label differs from prediction but the note is generic/uninformative ('Review whether this activity is a hazard warning or controlled airspace restriction.'); record the reason for the decision |
| 299 | VIDP A1100/26 | notes | label differs from prediction but the note is generic/uninformative ('Review severity against operational airspace/Q-code context; text indicates active airspace/range activity.'); record the reason for the decision |
| 300 | VOMM A2385/26 | notes | label differs from prediction but the note is generic/uninformative (''); record the reason for the decision |

## Warnings (aliases, normalisation, duplicates)

None.

## Prediction vs annotation disagreements

Category: 93 rows; severity: 132 rows (full list in annotation_audit.json). Disagreement is not evidence that the label is wrong.

| severity pair | rows |
|---|---|
| annotated RESTRICTIVE, predicted ADVISORY | 110 |
| annotated BLOCKING, predicted ADVISORY | 15 |
| annotated ADVISORY, predicted RESTRICTIVE | 4 |
| annotated RESTRICTIVE, predicted BLOCKING | 3 |