from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
from PIL import Image, ImageDraw
from skyfield.api import load, wgs84, Star
from skyfield.data import hipparcos

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

    with load.open(hipparcos.URL) as f:
        star_df = hipparcos.load_dataframe(f)

    star_df = star_df.dropna(subset=["ra_hours", "dec_degrees", "magnitude", "parallax_mas"])
    star_df = star_df[star_df["parallax_mas"] > 0]
    star_df = star_df[star_df["magnitude"] <= mag_limit]

    all_stars = Star.from_dataframe(star_df)

    t = ts.from_datetime(dt.astimezone(ZoneInfo("UTC")))
    observer = earth + wgs84.latlon(lat, lon)

    apparent = observer.at(t).observe(all_stars).apparent()
    alt, az, _ = apparent.altaz()

    alt_deg = alt.degrees
    az_deg = az.degrees
    magnitudes = star_df["magnitude"].values
    hip_ids = star_df.index.values  # HIP catalog numbers, needed to look up names

    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    for a, az_val, mag, hip_id in zip(alt_deg, az_deg, magnitudes, hip_ids):
        x, y = degrees_to_pixels_generic(az_val, a, width, height)

        radius = max(0.5, 3.5 - mag * 0.5)
        opacity = int(max(80, 255 - mag * 35))
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=(255, 255, 255, opacity),
        )

        # Only label bright, named stars to avoid clutter
        if mag <= label_mag_limit and hip_id in STAR_NAMES:
            name = STAR_NAMES[hip_id]
            draw.text((x + radius + 3, y - 5), name, fill=(255, 255, 50))

    img.save(f"icons/starmap_{event_name}.png")


def degrees_to_pixels_generic(az: float, alt: float, width: int, height: int) -> tuple:
    """Same conversion logic as your horizon image function, but parameterized by resolution."""
    az = az % 360
    x = int((az / 360) * width)
    y = int(((90 - alt) / 180) * height)
    return (x, y)