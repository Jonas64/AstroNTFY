import numpy as np
import py360convert
import pandas as pd
import requests
from skyfield.api import load, wgs84, Star
from datetime import datetime
from zoneinfo import ZoneInfo
from time import sleep
from PIL import Image, ImageDraw

from variables import *
from skymap_generation import generate_starmap

localtime = ZoneInfo(timezone)
ntfy_url = f"https://ntfy.sh/{topic}"

if include_observation_horizon:
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

def ra_dec_to_alt_az(ra:float, dec:str) -> tuple:
    ts = load.timescale()
    t = ts.now()

    eph = load("de421.bsp")
    earth = eph["earth"]

    observer = earth + wgs84.latlon(float(latitude), float(longitude))

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
    latitude_short = str(round(float(latitude), 3))
    longitude_short = str(round(float(longitude), 3))

    weather_forecast = requests.get(f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={latitude_short}&lon={longitude_short}&altitude={elevation}", headers={"User-Agent": "AstroNTFY"})
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

def generate_horizon_img(az:float, alt:float, name:str, time:datetime):
    """Creates and saves a flattened image of the horizon including a circle of where the event will happen"""
    az += horizon_north_offset
    az = az%360
    coords = degrees_to_pixels(az, alt)

    generate_starmap(float(latitude), float(longitude), time, name)

    horizon = Image.open("obs_horizon/horizon.png").convert("RGBA")
    starmap = Image.open(f"icons/starmap_{name}.png").convert("RGBA")
    horizon_img_draw = Image.alpha_composite(starmap.resize(horizon.size), horizon)

    draw = ImageDraw.Draw(horizon_img_draw)
    if get_visibility(az, alt):
        fill_color = "green"
    else:
        fill_color = "red"
    draw.circle((coords), 10, fill=fill_color)

    flat_np = py360convert.e2p(
        np.array(horizon_img_draw), 
        fov_deg=90, 
        u_deg=az-180, 
        v_deg=alt, 
        out_hw=(512, 512)
    )
    flat_img = Image.fromarray(flat_np.astype(np.uint8))
    flat_img.save("icons/"+name+".png")

def get_visibility(az:float, alt:float) -> bool:
    """
    Checks with the horizon 360 image if the inputted alt/az is blocked by obstacles or not
    """
    az += horizon_north_offset
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
