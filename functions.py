import numpy as np
import py360convert
import pandas as pd
import requests
import numpy as np
import math
from skyfield.api import load, wgs84, Star
from datetime import datetime
from zoneinfo import ZoneInfo
from time import sleep
from PIL import Image, ImageDraw, ImageFont

import variables as vb
import skymap_generation

localtime = ZoneInfo(vb.timezone)
ntfy_url = f"https://ntfy.sh/{vb.topic}"

font = ImageFont.truetype("Roboto-Regular.ttf", size=14)

if vb.include_observation_horizon:
    horizon = Image.open("obs_horizon/horizon.png").convert("RGBA")

def dms_to_decimal(dms_str: str) -> float:
    """
    Converts a DMS string like '-14:11:11.2' or '05:23:47.9' 
    into decimal degrees.
    """
    is_negative = dms_str.strip().startswith("-")
    
    # Strip the sign before splitting, so we work with clean positive parts
    clean_str = dms_str.strip().lstrip("+-")
    parts = clean_str.split(":")
    
    degrees = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    
    if is_negative:
        decimal = -decimal
    
    return decimal

def ra_dec_to_alt_az(ra:float, dec:str, time_utc:datetime) -> tuple:
    """Converts RA/Dec to Alt, Az. RA is in decimal, Dec is in DMS, returns in degrees"""
    if time_utc.tzinfo is None:
        raise ValueError("time_utc must be timezone-aware (e.g. tagged as UTC)")
    
    ts = load.timescale()
    t = ts.from_datetime(time_utc.astimezone(ZoneInfo("UTC")))

    eph = load("de421.bsp")
    earth = eph["earth"]

    observer = earth + wgs84.latlon(float(vb.latitude), float(vb.longitude))

    comet = Star(ra_hours=ra, dec_degrees=dms_to_decimal(dec))

    apparent = observer.at(t).observe(comet).apparent()
    alt, az, distance = apparent.altaz()

    return (float(alt.degrees), float(az.degrees))

def format_delta(delta) -> str:
    """Formats a timedelta as a signed, readable '+Dd Hh Mm' string."""
    total_seconds = delta.total_seconds()
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)

    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)

    parts = []
    if days > 0:
        if days == 1:
            parts.append(f"{days}day")
        else:
            parts.append(f"{days}days")
    if hours > 0 or days > 0:  # show hours if there are days, even if hours=0
        parts.append(f"{hours}h")
    parts.append(f"{minutes}min")

    return f"{sign}{' '.join(parts)}"

def weather() -> pd.DataFrame:
    """Fetches the weather forecast and returns it as a dataframe"""
    latitude_short = str(round(float(vb.latitude), 3))
    longitude_short = str(round(float(vb.longitude), 3))

    weather_forecast = requests.get(f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={latitude_short}&lon={longitude_short}&altitude={vb.elevation}", headers={"User-Agent": "AstroNTFY"})
    weather_forecast = weather_forecast.json()

    # Get weather forecast timeseries
    weather_data = weather_forecast["properties"]["timeseries"]
    weather_data = pd.DataFrame(weather_data)

    weather_data["time_utc"] = weather_data["time"].apply(lambda t: to_datetime_utc(t))

    # Extract data and create seperate collumns for it
    instant_details = weather_data["data"].apply(lambda x: x["instant"]["details"])
    instant_df = pd.json_normalize(instant_details)
    weather_data = pd.concat([weather_data.drop(columns=["data"]), instant_df], axis=1)

    return weather_data

def to_datetime_utc(time:str) -> datetime:
    """Returns the datetime object of a string in UTC time"""
    return datetime.fromisoformat(time)

def to_str_localtime(datetime_obj:datetime) -> str:
    """Returns a formatted readable string of the datetime UTC object in localtime"""
    local_datetime = datetime_obj.astimezone(localtime)
    datetime_str = local_datetime.strftime("%A, %d. %B at %H:%M (%Y)") #%Z")
    return datetime_str

def apply_north_offset(img: Image.Image, offset_deg: float) -> Image.Image:
    """Shifts the image horizontally so pixel x=0 corresponds to true north (az=0)."""
    width, height = img.size
    offset_px = int((offset_deg / 360) * width)

    img_np = np.array(img)
    shifted_np = np.roll(img_np, shift=offset_px, axis=1)  # axis=1 = horizontal roll
    return Image.fromarray(shifted_np)

def generate_horizon_img(az:float, alt:float, name:str, time:datetime, lat:float, lon:float):
    """Creates and saves a flattened image of the horizon including a circle of where the event will happen"""
    coords = degrees_to_pixels(az, alt)

    skymap_generation.generate_starmap(lat, lon, time, name)

    horizon = Image.open("obs_horizon/horizon.png").convert("RGBA")
    horizon = apply_north_offset(horizon, vb.horizon_north_offset)
    starmap = Image.open(f"starmaps/{name}.png").convert("RGBA")
    horizon_img_draw = Image.alpha_composite(starmap, horizon)#.resize(horizon.size), horizon)

    draw = ImageDraw.Draw(horizon_img_draw)
    draw.circle((coords), 2, fill=(255, 255, 255))
    if name == "comet":
        txt = "Comet"
        offset_x = 25
    else:
        txt = "ISS"
        offset_x = 35
    draw_equirectangular_text(horizon_img_draw, txt, (coords[0]-offset_x, coords[1]-3), alt, font)

    fov = 75
    res = 512
    flat_np = py360convert.e2p(
        np.array(horizon_img_draw), 
        fov_deg=fov, 
        u_deg=az-180, 
        v_deg=alt, 
        out_hw=(res, res)
    )
    flat_img = Image.fromarray(flat_np.astype(np.uint8))
    flat_img.save("icons/"+name+".png")

def draw_equirectangular_text(base_img, text, position, latitude_deg, font_):
    # 1. Convert latitude to radians
    lat_rad = math.radians(latitude_deg)
    
    # 2. Calculate the horizontal compression factor
    # This is the inverse of the map's stretching factor
    scale_x = 1/math.cos(lat_rad)
    
    # Avoid division or collapsing at the absolute poles
    if scale_x < 0.01: 
        scale_x = 0.01
        
    # 3. Create a temporary canvas for the text
    # Make it large enough to hold the uncompressed text
    
    # Get bounding box of the text to minimize canvas size
    dummy_img = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.textbbox((0, 0), text, font=font_)
    text_w = bbox[2] - bbox[0] + 20 # add padding
    text_h = bbox[3] - bbox[1] + 20
    
    txt_canvas = Image.new("RGBA", (text_w, text_h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_canvas)
    draw.text((10, 10), text, fill=(255, 255, 50), font=font_)
    
    # 4. Compress the text horizontally
    new_width = max(1, int(txt_canvas.width * scale_x))
    new_height = txt_canvas.height # Y size stays 1:1
    
    compressed_text = txt_canvas.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # 5. Paste onto your equirectangular image
    # Center the compressed text on your target position
    paste_x = position[0] - (new_width // 2)
    paste_y = position[1] - (new_height // 2)
    
    base_img.paste(compressed_text, (int(paste_x), int(paste_y)), compressed_text)

def get_visibility(az:float, alt:float) -> bool:
    """
    Checks with the horizon 360 image if the inputted alt/az is blocked by obstacles or not
    """
    az += vb.horizon_north_offset
    az = az%360
    coords = degrees_to_pixels(az, alt)
    r, g, b, a = horizon.getpixel(coords)

    return a < 100

def degrees_to_pixels(az:float, alt:float) -> tuple:
    """Converts alt/az to pixels"""
    width, height = horizon.size
    az = az % 360
    x = int((az / 360) * width)
    y = int(((90 - alt) / 180) * height)
    return (x, y)

def notify(message:str, headers:dict, local_icon:str, tries:int=0, limit_tries:int=5) -> bool:
    """Sends the post request to send a notification"""
    if local_icon != "":
        with open("icons/"+local_icon+".png", "rb") as img:
            response = requests.post(ntfy_url, data=img, headers=headers)
    else:
        response = requests.post(ntfy_url, data=message, headers=headers)

    if response.status_code == 200:
        print("Notification sent successfully!")
        return True
    else:
        print(f"Failed to send notification: {response.status_code}")
        if tries < limit_tries:
            sleep(10)
            notify(message, headers, tries+1)
        else:
            return False
