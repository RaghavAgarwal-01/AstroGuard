export const mockSatellites = [
  { name: "ISS", lat: 28.4, lon: -80.6, alt_km: 408 },
  { name: "Starlink-1", lat: 53.0, lon: 22.0, alt_km: 550 },
  { name: "Debris-1274", lat: 31.0, lon: -75.0, alt_km: 410 },
  { name: "NOAA-19", lat: -15.0, lon: 45.0, alt_km: 870 },
  { name: "Hubble", lat: 28.5, lon: -100.0, alt_km: 540 },
  { name: "Debris-807", lat: 60.0, lon: 30.0, alt_km: 400 },
  { name: "Aqua", lat: -40.0, lon: 150.0, alt_km: 705 },
  { name: "Debris-221", lat: 45.0, lon: -60.0, alt_km: 420 },
]

export const mockEvents = [
  {
    id: 0,
    obj_a: "ISS",
    obj_b: "Debris-1274",
    min_dist_km: 4.2,
    closest_time: "2026-06-14T18:32:00Z",
    rel_velocity_kms: 7.1
  },
  {
    id: 1,
    obj_a: "Starlink-1",
    obj_b: "Debris-807",
    min_dist_km: 11.8,
    closest_time: "2026-06-14T21:15:00Z",
    rel_velocity_kms: 5.3
  },
]