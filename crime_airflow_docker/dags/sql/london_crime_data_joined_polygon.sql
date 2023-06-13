SELECT
  ls.LSOA11NM lsoa_name,
  LSOA11CD lsoa_code,
  ls.MSOA11CD msoa_code,
  ls.MSOA11NM msoa_name,
  ls.LAD11CD lad_code,
  ls.LAD11NM lad_name,
  polygon lsoa_polygon,
  ST_GeogFromGeoJson(ms.geom,
    make_valid => TRUE) msoa_polygon,
  c.month,
  crime_id,
  coordinates,
  crime_type,
  last_outcome_category
FROM
  `gary-yiu-001.london.london_lsoa_polygon` ls
LEFT JOIN
  london.london_msoa ms
ON
  ls.MSOA11CD = ms.MSOA11CD
LEFT JOIN
  `gary-yiu-001.london.london_recent_crime_data` c
ON
  ls.LSOA11CD = c.lsoa_code