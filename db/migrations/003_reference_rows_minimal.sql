-- 003_reference_rows_minimal.sql  -- minimal FIR / airport reference rows
--
-- Purpose: notam_event.fir_code is a foreign key to fir, and relevant-NOTAM
-- retrieval needs the source/destination airport positions.  These rows let
-- Person A's pipeline and GET /notams/relevant run before Person B's
-- static_data loaders (OurAirports, FIR boundaries) have been executed.
--
-- * INSERT ... ON CONFLICT DO NOTHING: never overwrites rows that Person B's
--   loaders have already written; B's loaders may UPSERT over these rows.
-- * FIR boundaries are left NULL here (Person B: static_data/load_fir.py).
-- * Airport positions are approximate aerodrome reference points (about
--   +/-0.01 deg) taken from public sources (OurAirports); they are adequate for
--   a 150-300 NM corridor but should be replaced by B's loader.

INSERT INTO fir (icao_code, name) VALUES
  ('VIDF', 'Delhi FIR'),
  ('VABF', 'Mumbai FIR'),
  ('VECF', 'Kolkata FIR'),
  ('VOMF', 'Chennai FIR')
ON CONFLICT (icao_code) DO NOTHING;

INSERT INTO airport (icao_code, iata_code, name, city, fir_code, location)
SELECT v.icao, v.iata, v.name, v.city, v.fir, ST_SetSRID(ST_MakePoint(v.lon, v.lat), 4326)
FROM (VALUES
  -- test-corridor airports
  ('VIDP', 'DEL', 'Indira Gandhi International',            'Delhi',      'VIDF', 28.5665,  77.1031),
  ('VABB', 'BOM', 'Chhatrapati Shivaji Maharaj International','Mumbai',   'VABF', 19.0887,  72.8679),
  ('VOBL', 'BLR', 'Kempegowda International',               'Bengaluru',  'VOMF', 13.1979,  77.7063),
  ('VOMM', 'MAA', 'Chennai International',                  'Chennai',    'VOMF', 12.9900,  80.1693),
  ('VECC', 'CCU', 'Netaji Subhas Chandra Bose International','Kolkata',   'VECF', 22.6547,  88.4467),
  ('VISR', 'SXR', 'Srinagar',                               'Srinagar',   'VIDF', 33.9871,  74.7742),
  -- other aerodromes that appear in the AAI summaries
  ('VOHS', 'HYD', 'Rajiv Gandhi International',             'Hyderabad',  'VOMF', 17.2313,  78.4299),
  ('VOHY', NULL,  'Begumpet',                               'Hyderabad',  'VOMF', 17.4531,  78.4676),
  ('VAAH', 'AMD', 'Sardar Vallabhbhai Patel International', 'Ahmedabad',  'VABF', 23.0772,  72.6347),
  ('VIJP', 'JAI', 'Jaipur International',                   'Jaipur',     'VIDF', 26.8242,  75.8122),
  ('VILK', 'LKO', 'Chaudhary Charan Singh International',   'Lucknow',    'VIDF', 26.7606,  80.8893),
  ('VIAR', 'ATQ', 'Sri Guru Ram Dass Jee International',    'Amritsar',   'VIDF', 31.7096,  74.7973),
  ('VICG', 'IXC', 'Chandigarh',                             'Chandigarh', 'VIDF', 30.6735,  76.7885),
  ('VANP', 'NAG', 'Dr. Babasaheb Ambedkar International',   'Nagpur',     'VABF', 21.0922,  79.0472),
  ('VAPO', 'PNQ', 'Pune',                                   'Pune',       'VABF', 18.5821,  73.9197),
  ('VASU', 'STV', 'Surat',                                  'Surat',      'VABF', 21.1141,  72.7418),
  ('VOGO', 'GOI', 'Dabolim',                                'Goa',        'VABF', 15.3808,  73.8314),
  ('VOCI', 'COK', 'Cochin International',                   'Kochi',      'VOMF', 10.1520,  76.4019),
  ('VOTV', 'TRV', 'Thiruvananthapuram International',       'Thiruvananthapuram', 'VOMF', 8.4821, 76.9201),
  ('VOCL', 'CCJ', 'Calicut International',                  'Kozhikode',  'VOMF', 11.1368,  75.9553),
  ('VOML', 'IXE', 'Mangaluru International',                'Mangaluru',  'VOMF', 12.9613,  74.8901),
  ('VOCB', 'CJB', 'Coimbatore International',               'Coimbatore', 'VOMF', 11.0300,  77.0434),
  ('VOTR', 'TRZ', 'Tiruchirappalli International',          'Tiruchirappalli', 'VOMF', 10.7654, 78.7097),
  ('VOBZ', 'VGA', 'Vijayawada',                             'Vijayawada', 'VOMF', 16.5304,  80.7968),
  ('VOVZ', 'VTZ', 'Visakhapatnam',                          'Visakhapatnam', 'VOMF', 17.7212, 83.2245),
  ('VOPB', 'IXZ', 'Veer Savarkar International',            'Sri Vijaya Puram', 'VOMF', 11.6412, 92.7297),
  ('VEGT', 'GAU', 'Lokpriya Gopinath Bordoloi International','Guwahati',  'VECF', 26.1061,  91.5859),
  ('VEPT', 'PAT', 'Jay Prakash Narayan International',      'Patna',      'VECF', 25.5913,  85.0880),
  ('VEBS', 'BBI', 'Biju Patnaik International',             'Bhubaneswar','VECF', 20.2444,  85.8178),
  ('VEIM', 'IMF', 'Imphal International',                   'Imphal',     'VECF', 24.7600,  93.8967)
) AS v(icao, iata, name, city, fir, lat, lon)
ON CONFLICT (icao_code) DO NOTHING;
