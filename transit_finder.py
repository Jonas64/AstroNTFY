"""
transit_finder_optimized.py – ISS transits across the Sun and Moon

Main entry function:
    get_transit_dataframe(lat, lon, radius, days, name="ISS", start_time=None)

Returns:
    pandas.DataFrame with columns:
    [name, body, time_utc, alt, az, best_lat, best_lon, obs_dist_km, duration, body_az, body_alt]

Requirements:
    pip install skyfield requests numpy pandas
"""

import math
import sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import requests
from skyfield.api import load, wgs84, EarthSatellite
from skyfield.framelib import itrs

# ── Algorithm parameters ────────────────────────────────────────────────────
SUN_RADIUS_DEG = 0.2665
MOON_RADIUS_DEG = 0.2575
NORAD_ISS = 25544

COARSE_STEP_S = 15.0
APPROACH_DEG = 18.0      # must stay > (ISS peak ang. speed ~1.1 deg/s) * COARSE_STEP_S

FINE_STEP_S = 0.1        # fine-scan time step in seconds
FINE_WINDOW_S = 30       # fine-scan window (± seconds around each candidate)
DEDUP_S = 60             # candidates closer than this (same body) are merged

COARSE_WORKERS = 4       # thread count for coarse scan
FINE_WORKERS = 4         # thread count for fine scan across candidates

GRID_TARGET_SPACING_KM = 6.0   # max distance between adjacent grid points


# ── TLE retrieval ────────────────────────────────────────────────────────────

def fetch_tle(norad: int = NORAD_ISS) -> tuple[str, str, str]:
    """Fetch current ISS TLE from Celestrak GP API."""
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=TLE"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    lines = [ln.strip() for ln in r.text.splitlines() if ln.strip()]
    if len(lines) < 3:
        sys.exit("[Error] Unexpected TLE format from Celestrak")
    return lines[0], lines[1], lines[2]


# ── Geometry helpers ─────────────────────────────────────────────────────────

def observer_grid(lat: float, lon: float, radius_km: float,
                   target_spacing_km: float = GRID_TARGET_SPACING_KM):
    """Returns grid of (lat, lon) observer points across radius_km."""
    pts = [(lat, lon)]
    if radius_km <= 0.1:
        return pts

    n_rings = max(1, math.ceil(radius_km / target_spacing_km))

    for ring in range(1, n_rings + 1):
        ring_radius_km = (radius_km / n_rings) * ring
        circumference_km = 2 * math.pi * ring_radius_km
        points_this_ring = max(8, math.ceil(circumference_km / target_spacing_km))

        for i in range(points_this_ring):
            bearing_deg = (360.0 / points_this_ring) * i
            b = math.radians(bearing_deg)
            dlat = (ring_radius_km / 111.0) * math.cos(b)
            dlon = (ring_radius_km / (111.0 * math.cos(math.radians(lat)))) * math.sin(b)
            pts.append((lat + dlat, lon + dlon))

    return pts


def haversine_km(lat1, lon1, lat2, lon2):
    """Approximate great-circle distance in km."""
    return math.sqrt(
        ((lat2 - lat1) * 111.0) ** 2 +
        ((lon2 - lon1) * 111.0 * math.cos(math.radians(lat1))) ** 2
    )


# ── Stage 1: coarse scan ─────────────────────────────────────────────────────

def _coarse_scan_chunk(args):
    """Computes angular separations and altitudes via 3D ICRF vectors."""
    lat, lon, tt_chunk, eph_path, line1, line2, tle_name = args

    ts = load.timescale()
    eph = load(eph_path)
    iss = EarthSatellite(line1, line2, tle_name, ts)

    topos = wgs84.latlon(lat, lon)
    t_arr = ts.tt_jd(tt_chunk)

    r_obs = topos.at(t_arr).position.km
    norm_obs = np.linalg.norm(r_obs, axis=0, keepdims=True)
    u_up = r_obs / np.maximum(norm_obs, 1e-6)

    r_iss_geo = iss.at(t_arr).position.km
    r_sun_geo = (eph["sun"] - eph["earth"]).at(t_arr).position.km
    r_moon_geo = (eph["moon"] - eph["earth"]).at(t_arr).position.km

    v_iss = r_iss_geo - r_obs
    v_sun = r_sun_geo - r_obs
    v_moon = r_moon_geo - r_obs

    norm_iss = np.linalg.norm(v_iss, axis=0)
    norm_sun = np.linalg.norm(v_sun, axis=0)
    norm_moon = np.linalg.norm(v_moon, axis=0)

    sin_alt_iss = np.einsum('ij,ij->j', v_iss, u_up) / np.maximum(norm_iss, 1e-6)
    sin_alt_sun = np.einsum('ij,ij->j', v_sun, u_up) / np.maximum(norm_sun, 1e-6)
    sin_alt_moon = np.einsum('ij,ij->j', v_moon, u_up) / np.maximum(norm_moon, 1e-6)

    iss_alt = np.degrees(np.arcsin(np.clip(sin_alt_iss, -1.0, 1.0)))
    sun_alt = np.degrees(np.arcsin(np.clip(sin_alt_sun, -1.0, 1.0)))
    moon_alt = np.degrees(np.arcsin(np.clip(sin_alt_moon, -1.0, 1.0)))

    cos_sep_sun = np.einsum('ij,ij->j', v_iss, v_sun) / np.maximum(norm_iss * norm_sun, 1e-6)
    cos_sep_moon = np.einsum('ij,ij->j', v_iss, v_moon) / np.maximum(norm_iss * norm_moon, 1e-6)

    sep_sun = np.degrees(np.arccos(np.clip(cos_sep_sun, -1.0, 1.0)))
    sep_moon = np.degrees(np.arccos(np.clip(cos_sep_moon, -1.0, 1.0)))

    return iss_alt, sun_alt, moon_alt, sep_sun, sep_moon


def coarse_scan(
    lat: float, lon: float, days: int, ts, eph, iss,
    line1: str, line2: str, tle_name: str, eph_path: str,
    start_time=None,
):
    t0 = ts.from_datetime(start_time) if start_time else ts.now()
    n = int(days * 86400 / COARSE_STEP_S) + 1
    tt = t0.tt + np.arange(n) * (COARSE_STEP_S / 86400.0)

    chunks = np.array_split(tt, COARSE_WORKERS)
    args = [(lat, lon, chunk, eph_path, line1, line2, tle_name) for chunk in chunks]

    with ThreadPoolExecutor(max_workers=COARSE_WORKERS) as ex:
        results = list(ex.map(_coarse_scan_chunk, args))

    iss_alt = np.concatenate([r[0] for r in results])
    sun_alt = np.concatenate([r[1] for r in results])
    moon_alt = np.concatenate([r[2] for r in results])
    sep_sun = np.concatenate([r[3] for r in results])
    sep_moon = np.concatenate([r[4] for r in results])

    iss_up = iss_alt > 0
    sun_up = sun_alt > -5
    moon_up = moon_alt > -5

    def extract_candidates(mask, sep_arr, body_name):
        idx = np.where(mask)[0]
        if len(idx) == 0:
            return []
        splits = np.where(np.diff(idx) > 1)[0] + 1
        runs = np.split(idx, splits)
        out = []
        for run in runs:
            best_idx = run[np.argmin(sep_arr[run])]
            out.append((float(tt[best_idx]), body_name))
        return out

    candidates = (
        extract_candidates(iss_up & sun_up & (sep_sun < APPROACH_DEG), sep_sun, "sun")
        + extract_candidates(iss_up & moon_up & (sep_moon < APPROACH_DEG), sep_moon, "moon")
    )
    candidates.sort(key=lambda x: x[0])

    deduped = []
    last_t = {}
    for t_c, body in candidates:
        if body not in last_t or (t_c - last_t[body]) * 86400 > DEDUP_S:
            deduped.append((t_c, body))
        last_t[body] = t_c

    return deduped


# ── Stage 2: vectorized fine scan ───────────────────────────────────────────

def fine_scan_radius(
    t_cand_tt: float, body_name: str,
    center_lat: float, center_lon: float, radius_km: float,
    ts, eph, iss,
):
    grid = observer_grid(center_lat, center_lon, radius_km)
    if not grid:
        return None

    body_eph = eph["sun"] if body_name == "sun" else eph["moon"]
    r_deg = SUN_RADIUS_DEG if body_name == "sun" else MOON_RADIUS_DEG

    n_fine = int(2 * FINE_WINDOW_S / FINE_STEP_S)
    tt = (t_cand_tt - FINE_WINDOW_S / 86400.0) + np.arange(n_fine) * (FINE_STEP_S / 86400.0)
    t_arr = ts.tt_jd(tt)

    r_iss = iss.at(t_arr).frame_xyz(itrs).km
    r_body = (body_eph - eph["earth"]).at(t_arr).frame_xyz(itrs).km

    grid_lats = np.array([p[0] for p in grid])
    grid_lons = np.array([p[1] for p in grid])
    topos_grid = wgs84.latlon(grid_lats, grid_lons)
    r_obs = topos_grid.itrs_xyz.km

    v_iss = r_iss[:, np.newaxis, :] - r_obs[:, :, np.newaxis]
    v_body = r_body[:, np.newaxis, :] - r_obs[:, :, np.newaxis]

    norm_obs = np.linalg.norm(r_obs, axis=0, keepdims=True)
    u_up = r_obs / np.maximum(norm_obs, 1e-6)

    norm_iss = np.linalg.norm(v_iss, axis=0)
    norm_body = np.linalg.norm(v_body, axis=0)

    cos_zenith_iss = np.einsum('imn,im->mn', v_iss, u_up) / np.maximum(norm_iss, 1e-6)
    cos_zenith_body = np.einsum('imn,im->mn', v_body, u_up) / np.maximum(norm_body, 1e-6)

    valid = (cos_zenith_iss > 0.0) & (cos_zenith_body > -0.087)

    dot = np.einsum('imn,imn->mn', v_iss, v_body)
    cos_sep = np.clip(dot / np.maximum(norm_iss * norm_body, 1e-6), -1.0, 1.0)
    sep_deg = np.degrees(np.arccos(cos_sep))
    sep_deg[~valid] = 999.0

    min_sep = float(np.min(sep_deg))
    if min_sep >= r_deg:
        return None

    m_best, n_best = np.unravel_index(np.argmin(sep_deg), sep_deg.shape)
    best_lat, best_lon = grid[m_best]

    in_disk = valid[m_best, :] & (sep_deg[m_best, :] < r_deg)
    duration_s = float(np.sum(in_disk)) * FINE_STEP_S
    t_transit = t_arr[n_best]

    topos_best = wgs84.latlon(best_lat, best_lon)
    obs_best = eph["earth"] + topos_best
    iss_alt, iss_az, _ = (iss - topos_best).at(t_transit).altaz()
    b_alt, b_az, _ = obs_best.at(t_transit).observe(body_eph).apparent().altaz()

    return {
        "body": body_name,
        "time_utc": t_transit.utc_datetime(),
        "iss_alt": float(iss_alt.degrees),
        "iss_az": float(iss_az.degrees),
        "best_lat": best_lat,
        "best_lon": best_lon,
        "obs_dist_km": haversine_km(center_lat, center_lon, best_lat, best_lon),
        "duration": round(duration_s, 2),
        "body_az": float(b_az.degrees),
        "body_alt": float(b_alt.degrees),
    }


# ── Main Entry Function ───────────────────────────────────────────────────────

def get_transit_dataframe(
    lat: float,
    lon: float,
    radius: float,
    days: int,
    name: str = "ISS",
    start_time=None,
) -> pd.DataFrame:
    """
    Search for satellite transits and return a pandas DataFrame.
    
    Columns returned:
      name, body, time_utc, iss_alt, iss_az, best_lat, best_lon, obs_dist_km, duration, body_az, body_alt
    """
    columns = [
        "name", "body", "time_utc", "iss_alt", "iss_az",
        "best_lat", "best_lon", "obs_dist_km", "duration",
        "body_az", "body_alt"
    ]

    tle_name, line1, line2 = fetch_tle()
    ts = load.timescale()
    eph_path = "de421.bsp"
    eph = load(eph_path)
    iss = EarthSatellite(line1, line2, tle_name, ts)

    candidates = coarse_scan(
        lat, lon, days, ts, eph, iss, line1, line2, tle_name, eph_path, start_time
    )

    if not candidates:
        return pd.DataFrame(columns=columns)

    def _scan_worker(cand):
        t_cand, body = cand
        return fine_scan_radius(t_cand, body, lat, lon, radius, ts, eph, iss)

    workers = min(FINE_WORKERS, len(candidates))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(_scan_worker, candidates))

    rows = []
    for r in results:
        if r is not None:
            rows.append({
                "name": name,
                "body": r["body"],
                "time_utc": r["time_utc"],
                "iss_alt": r["iss_alt"],
                "iss_az": r["iss_az"],
                "best_lat": r["best_lat"],
                "best_lon": r["best_lon"],
                "obs_dist_km": r["obs_dist_km"],
                "duration": r["duration"],
                "body_az": r["body_az"],
                "body_alt": r["body_alt"],
            })

    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df.sort_values(by="time_utc", inplace=True)
        df.reset_index(drop=True, inplace=True)

    return df