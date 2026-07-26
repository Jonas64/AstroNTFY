from datetime import datetime
from zoneinfo import ZoneInfo
import math
from PIL import Image, ImageDraw, ImageFont
from skyfield.api import load, wgs84, Star
from skyfield.data import hipparcos
import numpy as np
import functions
import variables

font = ImageFont.truetype("Roboto-Regular.ttf", size=12)
bigger_font = ImageFont.truetype("Roboto-Regular.ttf", size=16)

STAR_NAMES = {
    32349: "Sirius",
    30438: "Canopus",
    69673: "Arcturus",
    91262: "Vega",
    24436: "Rigel",
    27989: "Betelgeuse",
    37279: "Procyon",
    7588: "Achernar",
    68702: "Hadar",
    97649: "Altair",
    21421: "Aldebaran",
    65474: "Spica",
    80763: "Antares",
    37826: "Pollux",
    113368: "Fomalhaut",
    49669: "Regulus",
    102098: "Deneb",
    11767: "Polaris",
    5447: "Mirach",
    25336: "Bellatrix",
}


def generate_starmap(
    lat: float,
    lon: float,
    dt: datetime,
    event_name: str,
    resolution: tuple = (2048, 1024),
    mag_limit: float = 4.0,
    label_mag_limit: float = 1.6,
) -> Image.Image:
    width, height = resolution

    ts = load.timescale()
    eph = load("de421.bsp")
    earth = eph["earth"]

    sun = eph['sun']
    moon = eph['moon']

    observer = earth + wgs84.latlon(lat, lon)
    t = ts.from_datetime(dt.astimezone(ZoneInfo("UTC")))

    # Get apparent Alt, Az, and distance from Earth
    sun_alt, sun_az, distance = observer.at(t).observe(sun).apparent().altaz()
    moon_alt, moon_az, distance = observer.at(t).observe(moon).apparent().altaz()

    with load.open(hipparcos.URL) as f:
        star_df = hipparcos.load_dataframe(f)

    star_df = star_df.dropna(subset=["ra_hours", "dec_degrees", "magnitude", "parallax_mas"])
    star_df = star_df[star_df["parallax_mas"] > 0]
    star_df = star_df[star_df["magnitude"] <= mag_limit]

    all_stars = Star.from_dataframe(star_df)

    apparent = observer.at(t).observe(all_stars).apparent()
    alt, az, _ = apparent.altaz()

    alt_deg = alt.degrees
    az_deg = az.degrees
    magnitudes = star_df["magnitude"].values
    hip_ids = star_df.index.values  # HIP catalog numbers, needed to look up names

    img = generate_sky_hdri(2048, 1024, sun_az.degrees, sun_alt.degrees).convert("RGBA")
    star_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_stars = ImageDraw.Draw(star_layer)
    
    global_star_opacity = translate(sun_alt.degrees, -6, 2.5, 1, 0)
    if global_star_opacity > 0:
        for a, az_val, mag, hip_id in zip(alt_deg, az_deg, magnitudes, hip_ids):
            x, y = degrees_to_pixels_generic(az_val, a, width, height)

            radius = max(0.5, 1.5 - mag * 0.15)
            opacity = max(50, 255 - mag * 60)
            diameter_x = (radius*2)*(1/math.cos(math.radians(a)))
            radius_x = diameter_x/2
            draw_stars.ellipse(
                [x - radius_x, y - radius, x + radius_x, y + radius],
                fill=(255, 255, 255, int(opacity*global_star_opacity)),
            )

            # Only label bright, named stars to avoid clutter
            if mag <= label_mag_limit and hip_id in STAR_NAMES:
                name = STAR_NAMES[hip_id]
                functions.draw_equirectangular_text(star_layer, name, (x + radius + (len(name)*7), y - 3), a, font)
    
    img = Image.alpha_composite(img, star_layer)
    draw = ImageDraw.Draw(img, "RGBA")

    sun_x, sun_y = degrees_to_pixels_generic(sun_az.degrees, sun_alt.degrees, width, height)
    moon_x, moon_y = degrees_to_pixels_generic(moon_az.degrees, moon_alt.degrees, width, height)
    sun_radius = 5
    sun_x_radius = ((sun_radius*2)*(1/math.cos(sun_alt.radians)))/2
    moon_radius = 5
    moon_x_radius = ((moon_radius*2)*(1/math.cos(moon_alt.radians)))/2
    draw.ellipse(
        [sun_x - sun_x_radius, (sun_y - sun_radius), (sun_x + sun_x_radius), sun_y + sun_radius],
        fill=(255, 209, 26),
    )
    functions.draw_equirectangular_text(img, "Sun", (sun_x+40, sun_y-3), sun_alt.degrees, bigger_font)
    draw.ellipse(
        [moon_x - moon_x_radius, (moon_y - moon_radius), (moon_x + moon_x_radius), moon_y + moon_radius],
        fill=(140, 140, 140),
    )
    functions.draw_equirectangular_text(img, "Moon", (moon_x+55, moon_y-3), moon_alt.degrees, bigger_font)

    img.save(f"starmaps/{event_name}.png")

def translate(value, leftMin, leftMax, rightMin, rightMax):
    # Figure out how 'wide' each range is
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin

    # Convert the left range into a 0-1 range (float)
    valueScaled = float(value - leftMin) / float(leftSpan)

    # Convert the 0-1 range into a value in the right range.
    return rightMin + (valueScaled * rightSpan)

def generate_sky_hdri(
    width: int,
    height: int,
    sun_azimuth: float,    # 0 to 360 degrees (0 = True North / Left edge)
    sun_altitude: float,   # -90 to +90 degrees (90 = Zenith, 0 = Horizon)
) -> Image.Image:
    """
    Generates a full 360x180 equirectangular sky map (without ground).
    
    Parameters:
        width, height: Resolution of target image (e.g., 2048, 1024)
        sun_azimuth: Sun direction in degrees (0..360)
        sun_altitude: Sun elevation in degrees (-90..90)
    """
    # 1. Generate Equirectangular Coordinate Grid
    # x -> Azimuth (0 to 2*pi), y -> Altitude (pi/2 to -pi/2)
    u = (np.arange(width) + 0.5) / width * 2 * np.pi
    v = (0.5 - (np.arange(height) + 0.5) / height) * np.pi
    AZ, ALT = np.meshgrid(u, v)

    # Spherical coordinates to 3D unit vectors for every pixel
    Vx = np.cos(ALT) * np.sin(AZ)
    Vy = np.cos(ALT) * np.cos(AZ)
    Vz = np.sin(ALT)

    # 2. Convert Sun Position to 3D Unit Vector
    sun_az_rad = np.radians(sun_azimuth)
    sun_alt_rad = np.radians(sun_altitude)
    
    Sx = np.cos(sun_alt_rad) * np.sin(sun_az_rad)
    Sy = np.cos(sun_alt_rad) * np.cos(sun_az_rad)
    Sz = np.sin(sun_alt_rad)

    # Cosine of angular distance between pixel vector and Sun vector
    cos_gamma = np.clip(Vx * Sx + Vy * Sy + Vz * Sz, -1.0, 1.0)
    angular_dist = np.arccos(cos_gamma)  # in radians

    # 3. Dynamic Palette Determination based on Sun Altitude
    alt = sun_altitude

    if alt > 15:  # Midday / Bright Day
        zenith_c  = np.array([30, 110, 225], dtype=float)
        horizon_c = np.array([170, 210, 245], dtype=float)
        sunset_c  = np.array([255, 240, 200], dtype=float)
        sun_core  = np.array([255, 255, 250], dtype=float)
        glow_factor = 0.3
    elif alt > 0:  # Golden Hour / Sunset
        t = alt / 15.0  # Interpolation factor 0..1
        zenith_c  = (1 - t) * np.array([20, 45, 95]) + t * np.array([30, 110, 225])
        horizon_c = (1 - t) * np.array([245, 125, 55]) + t * np.array([170, 210, 245])
        sunset_c  = (1 - t) * np.array([255, 60, 20]) + t * np.array([255, 240, 200])
        sun_core  = np.array([255, 235, 180], dtype=float)
        glow_factor = 1.0
    elif alt > -6:  # Civil Twilight
        t = (alt + 6.0) / 6.0
        zenith_c  = (1 - t) * np.array([8, 15, 40]) + t * np.array([20, 45, 95])
        horizon_c = (1 - t) * np.array([110, 40, 55]) + t * np.array([245, 125, 55])
        sunset_c  = (1 - t) * np.array([180, 50, 25]) + t * np.array([255, 60, 20])
        sun_core  = np.array([255, 120, 50], dtype=float)
        glow_factor = 0.8
    else:  # Night / Deep Twilight
        zenith_c  = np.array([3, 5, 15], dtype=float)
        horizon_c = np.array([10, 18, 35], dtype=float)
        sunset_c  = np.array([25, 15, 30], dtype=float)
        sun_core  = np.array([40, 20, 25], dtype=float)
        glow_factor = 0.1

    # 4. Render Continuous Sky Gradient (Zenith down to Nadir)
    # Altitude mask [0..1] above horizon. Below horizon (ALT < 0) stays horizon_c
    sky_mask = np.clip(ALT / (np.pi / 2), 0, 1)
    
    # Non-linear curve pushing horizon color down smoothly
    sky_gradient = np.power(sky_mask, 0.4)[:, :, np.newaxis]
    
    # Base sky color blend
    sky = (1.0 - sky_gradient) * horizon_c + sky_gradient * zenith_c

    # 5. Render Directional Sunset / Sun Glow
    # Atmospheric glow around sun
    glow_intensity = np.exp(-3.0 * angular_dist) * glow_factor
    
    # Symmetrical horizon bias so sunset glow bleeds smoothly above & below 0° altitude
    horizon_bias = np.clip(1.0 - np.abs(ALT) / (np.pi / 3), 0, 1)
    
    sun_glow = glow_intensity[:, :, np.newaxis] * sunset_c * horizon_bias[:, :, np.newaxis]
    sky += sun_glow

    # 6. Render Sun Disc
    sun_disc_radius = np.radians(1.2)
    sun_disc_mask = (angular_dist < sun_disc_radius)[:, :, np.newaxis]
    sky = np.where(sun_disc_mask, sun_core, sky)

    # 7. Convert to 8-bit PIL Image
    rgb_img = np.clip(sky, 0, 255).astype(np.uint8)
    return Image.fromarray(rgb_img, mode="RGB")

def degrees_to_pixels_generic(az: float, alt: float, width: int, height: int) -> tuple:
    """Same conversion logic as your horizon image function, but parameterized by resolution."""
    az = az % 360
    x = int((az / 360) * width)
    y = int(((90 - alt) / 180) * height)
    return (x, y)