SELECT 
  Crime_ID AS crime_id,
  Month AS month,
  DATE_ADD(PARSE_DATE('%Y-%m', Month), INTERVAL 1 MONTH) AS date_month,
  Reported_by As reported_by,
  Falls_within AS falls_within,
  ST_GEOGPOINT(Longitude, Latitude) AS coordinates,
  Location AS location,
  LSOA_code AS lsoa_code,
  LSOA_name AS lsoa_name,
  Crime_type AS crime_type,
  Last_outcome_category AS last_outcome_category
FROM `gary-yiu-001.london.london_recent_crime_data_raw`
WHERE Crime_ID IS NOT NULL AND location <> 'No Location'
