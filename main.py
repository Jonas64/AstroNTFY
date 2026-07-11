import requests
from datetime import datetime
from datetime import timezone as tz
from zoneinfo import ZoneInfo
import pandas
from time import sleep
from variables import *


translate_months = {
    "01": "January",
    "02": "February",
    "03": "March",
    "04": "April",
    "05": "May",
    "06": "June",
    "07": "July",
    "08": "August",
    "09": "September",
    "10": "October",
    "11": "November",
    "12": "December"
}
translate_months_reverse = dict(zip(translate_months.values(), translate_months.keys()))


transit_url = f"https://issinfo.net/transit-finder?lat={latitude}&lon={longitude}&days=30"
northern_lights_url = "https://www.nordlysvarsel.com/en/"
sun_url = "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_2048_HMIIF.jpg"
comet_url = "https://theskylive.com/"

northern_lights_img_url = "https://www.dropbox.com/scl/fi/vfdq084syxys7b6n9jhmq/northern_lights.jpg?rlkey=pmo8l094bzjv1vn5cm5z10rf9&st=76hp8qps&dl=1"
comet_img_url = "https://www.dropbox.com/scl/fi/06p5j4foc4j72t2hxepe1/comet.jpg?rlkey=ssmvrl1sd1b7atub3v6dx70g3&st=jz64u6cp&dl=1"
sun_img_url = "https://www.dropbox.com/scl/fi/f0uw2qs5th3hnx2bbm2ix/sun.jpg?rlkey=pjzfahajf2yy9fewhd5yztp7q&st=38qhs911&dl=1"
lunar_transit_img_url = "https://www.dropbox.com/scl/fi/grjasntzv3g5m4190wduc/lunar_transit.png?rlkey=cw26ju1xdxz9jucvufg4q2xhx&st=iv4om1ef&dl=1"
solar_transit_img_url = "https://www.dropbox.com/scl/fi/5hkcb42pi1gopd1a4hsah/solar_transit.png?rlkey=7i4hiq023y95gidz2l6k7r3bj&st=kuloh7hs&dl=1"

ntfy_url = f"https://ntfy.sh/{topic}"
notification_priority = "3"

def convert_time(time_str_iso_8601_utc:str) -> tuple:
    dt_utc = datetime.fromisoformat(time_str_iso_8601_utc)

    # Convert to local time zone
    date_local = dt_utc.astimezone(ZoneInfo(timezone))

    # Format to a readable local string including day
    formatted = date_local.strftime("%A, %d. %B at %H:%M (%Y) %Z")

    # Sunday, 12. July at 23:00 (2026)
    return (formatted, date_local)

def notify(message:str, headers:dict, tries:int=0, limit_tries:int=10):
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

def check_northern_lights(weather_df_:pandas.DataFrame, notify_:bool=True, print_message:bool=False) -> dict:
    all_data = requests.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json")
    all_data = all_data.json()
    forecast = []
    for data_point in all_data:
        if data_point["observed"] != "observed": # If datapoint is a prediction, not observation
            time = convert_time(data_point["time_tag"])
            forecast.append({
                "time_str": time[0],
                "raw_time": time[1],
                "kp": data_point["kp"],
                "noaa_scale": data_point["noaa_scale"]
            })

    notify_northern_lights(forecast, weather_df_, notify_, print_message)

    return forecast

def notify_northern_lights(forecast:list, weather_df_:pandas.DataFrame, notify_:bool=True, print_message:bool=False):
    forecast_df = pandas.DataFrame(forecast)
    
    max_kp = max(forecast_df["kp"])
    max_kp_index = (forecast_df["kp"] == max_kp).idxmax() # Index for the max kp of all predictions

    print(forecast[max_kp_index]["time_str"])
    print()

    if max_kp > kp_treshold:
        message = f"Predictions show a chance of kp {max_kp} on {forecast_df["time_str"][max_kp_index]}"
        
        headers = {
            "Title": f"Chance for northern lights (kp {max_kp})",
            "Click": northern_lights_url,
            "Priority": notification_priority,
            "X-Attach": northern_lights_img_url
        }
        
        forecast = generate_weather_forecast({"date": str(forecast[max_kp_index]["raw_time"])[:10], "time": str(forecast[max_kp_index]["raw_time"])[11:16]}, weather_df_)
        message += forecast

        if print_message:
            print(message)
        if notify_:
            notify(message, headers)
    else:
        print("No northern light activity.")

def check_transits(weather_df_:pandas.DataFrame, notify_:bool=True, print_message:bool=False) -> dict:
    latitude = 10
    transits = requests.get(f"https://issinfo.net/api/transits-proxy?lat={latitude}&lon={longitude}&body=both&days=30&max_drive_km=50&visible_only=true")
    transits = transits.json()
    
    if transits["count"] > 0:
        all_satellite_names = []
        all_bodies = []
        all_times = []
        for transit in transits["transits"]:
            all_satellite_names.append(transit["satellite_name"])
            all_bodies.append(transit["body"])
            all_times.append(datetime.fromtimestamp(transit["utc_unix"], tz=ZoneInfo(timezone)))
        if notify_:
            notify_transit(transits["count"], all_satellite_names, all_bodies, all_times, weather_df_, print_message)

    return transits

def notify_transit(transit_count:int, transit_station:list, body:list, time:list, weather_df_:pandas.DataFrame, print_message:bool=False):
    if body[0] == "moon":
        title = "Lunar transit"
        transit_img_url = lunar_transit_img_url
    else:
        title = "Solar transit"
        transit_img_url = solar_transit_img_url
    if transit_count > 1:
        title = "Multiple transits"

    formatted_time = ""
    time[0] = str(time[0])
    formatted_time += time[0][:5]

    headers = {
        "Title": title,
        "Click": transit_url,
        "Priority": notification_priority,
        "X-Attach": transit_img_url
    }
    if transit_count == 1:
        message = title+f" ({transit_station[0]})"
    elif transit_count > 1:
        transit_stations_str = ""
        for station in transit_station:
            if station not in transit_stations_str:
                transit_stations_str += station+" x"+str(transit_station.count(station))+", "
        transit_stations_str = transit_stations_str[:-2]
        message = title+f" ({transit_stations_str})"

    forecast = generate_weather_forecast({"date": time[0][:10], "time": time[0][11:16]}, weather_df_)
    
    message += forecast

    if print_message:
        print(message)
    
    if transit_count > 0:
        notify(message, headers)
    else:
        print("No future transits.")

def remove_from_list(l:list, r) -> list:
    for row in l:
        while r in row:
            row.remove(r)
    return l

def check_solar_activity(print_message:bool=False) -> dict:
    solar_activity = requests.get("https://services.swpc.noaa.gov/text/solar-regions.txt").text

    text_rows = solar_activity.split("\n")

    data_rows = []
    for i, row in enumerate(text_rows): # Remove info, keep sunspot table
        if i > 11:
            data_rows.append(row.split(" "))
    
    clean_data_rows = remove_from_list(data_rows, "")
    clean_data_rows.remove([])

    final_data = []
    for row in clean_data_rows:
        final_data.append({
            "Area": int(row[3]),
            "Extent": int(row[4]),
            "Class": row[5],
            "Local count": int(row[6])
        })

    notify_solar_activity(final_data, print_message)
    
    return final_data

def notify_solar_activity(sunspots:dict, print_message:bool=False):
    sunspots_df = pandas.DataFrame(sunspots)

    sum_area = sum(sunspots_df["Area"])
    big_sunspot_count = sum(sunspots_df["Area"] > 250)

    if sum_area > total_sunspot_area_treshold:
        if big_sunspot_count == 1:
            message = f"There is {big_sunspot_count} big sunspot on the sun, total area of all spots, {sum_area}"
        else:
            message = f"There are {big_sunspot_count} big sunspots on the sun, total area of all spots, {sum_area}"

        headers = {
            "Title": "Potentially multiple (big) sunspots",
            "Click": sun_url,
            "Priority": notification_priority,
            "X-Attach": sun_img_url
        }

        if print_message:
            print(message)

        notify(message, headers)
    else:
        print("No notable solar activity.")

def check_comets(date_to_check:str, weather_df_:pandas.DataFrame, notify_:bool=True, print_message:bool=False) -> dict:
    comet_data = requests.get(f"https://cobs.si/data/planner/?session_date={date_to_check}&sun_alt=15&name=Oslo&lat={latitude}&long={longitude}&elev={elevation}&tz=localtime&mag={comet_mag_treshold}&alt=10&sun_elong=0&moon_elong=0&filter=0&_=1783448627942")

    comet_data = comet_data.json()
    comet_data = comet_data["data"]

    if len(comet_data) > 0:
        if notify_:
            notify_comets(comet_data, weather_df_, print_message)
    else:
        print("No notable bright/visable comets.")

def notify_comets(comets:dict, weather_df_:pandas.DataFrame, print_message:bool=False):
    comets_df = pandas.DataFrame(comets)
    highest_mag_comet = comets_df.loc[comets_df["magnitude"].idxmax()]
    
    comet_magnitude = highest_mag_comet["magnitude"]        # Magnitude of comet
    best_viewing_time = highest_mag_comet["best_time"]      # Best time to view from Oslo
    comet_fullname = highest_mag_comet["comet_fullname"]    # Full name of comet
    comet_name = highest_mag_comet["comet_name"].lower()    # Official name
    altitude = highest_mag_comet["best_alt"]                # Highest point it will be in the sky

    message = f"Comet {comet_fullname} with a magnitude of {comet_magnitude} and altitude {altitude} will be the most visable at {best_viewing_time}"

    headers = {
        "Title": "Potentially visable comet.",
        "Click": f"{comet_url}{comet_name}-info",
        "Priority": notification_priority,
        "X-Attach": comet_img_url
    }
    forecast = generate_weather_forecast({"date": best_viewing_time[:10], "time": best_viewing_time[-5:]}, weather_df_)
    message += forecast

    if print_message:
        print(message)

    notify(message, headers)

import json

def check_weather() -> pandas.DataFrame:
    latitude_short = round(float(latitude), 3)
    longitude_short = round(float(longitude), 3)
    """
    weather_forecast = requests.get(f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={latitude_short}&lon={longitude_short}&altitude={elevation}")
    weather_forecast = weather_forecast.json()

    with open("weather.json", "w", encoding="utf-8") as f:
        json.dump(weather_forecast, f, indent=4)
    """

    with open("weather.json", "r") as f:
        weather_forecast = json.load(f)
    
    weather_data = weather_forecast["properties"]["timeseries"]
    weather_df_ = pandas.DataFrame(weather_data)

    # Convert time from ISO8601 to localtime and readable str
    weather_df_["time_str"] = weather_df_["time"].apply(lambda t: convert_time(t)[0])
    weather_df_["raw_time"] = weather_df_["time"].apply(lambda t: convert_time(t)[1])

    # Extract data and create seperate collumns for it
    instant_details = weather_df_["data"].apply(lambda x: x["instant"]["details"])
    instant_df = pandas.json_normalize(instant_details)
    weather_df_ = pandas.concat([weather_df_.drop(columns=["data"]), instant_df], axis=1)

    return weather_df_

def closest_weather_forecast(weather_df_:pandas.DataFrame, check_time:dict) -> pandas.DataFrame:
    # Format check time
    str_check_time = check_time["date"]+" "+check_time["time"]+":00"+" +0000" # "2026-07-10 14:30:00"
    datetime_check_time = datetime.strptime(str_check_time, "%Y-%m-%d %H:%M:%S %z")
    print(datetime_check_time)

    # Format time in dataframe
    weather_df_["time"] = weather_df_["raw_time"]
    print(weather_df_["time"])

    # Sort delta time to find lowest time difference
    weather_df_["delta_time"] = weather_df_["time"].apply(lambda t: t.to_pydatetime()-datetime_check_time)
    weather_df_["delta_time"] = weather_df_["delta_time"].apply(lambda t: abs(t))
    weather_df_ = weather_df_.sort_values(by="delta_time", ignore_index=False, key=abs)

    return weather_df_.head(1)

def generate_weather_forecast(check_time:dict, all_forecasts:pandas.DataFrame) -> str:
    """
    check_time = {
        'date': '2026-07-12',
        'time': '01:22'
    }
    """
    closest_forecast = closest_weather_forecast(all_forecasts, check_time)
    closest_forecast_all = all_forecasts.loc[closest_forecast.index[0]]
    closest_forecast_all["delta_time"] = str(closest_forecast_all["delta_time"])[:-3]
    sign = closest_forecast_all["delta_time"][0]
    if closest_forecast_all["delta_time"][0] == "0":
        closest_forecast_all["delta_time"] = closest_forecast_all["delta_time"][-5:]
    if sign != "-":
        closest_forecast_all["delta_time"] = "+"+closest_forecast_all["delta_time"]
    
    forecast = f"\n\nHere is the closest weather forecast available ({closest_forecast_all["delta_time"]}):\n"

    forecast += f"Cloud coverage: {closest_forecast_all["cloud_area_fraction"]} %\n"
    forecast += f"Wind speed: {closest_forecast_all["wind_speed"]} m/s"

    return forecast

weather_df = check_weather()
check_northern_lights(weather_df, notify_=False, print_message=True)

#transits = check_transits(weather_df, notify_=False, print_message=True)
#check_comets(date.today(), weather_df, notify_=False, print_message=True)

month = datetime.now().month
if (month >= 3) and (month <= 9):   # Between march and september (summer)
    #check_solar_activity(weather_df, notify_=False, print_message=True)
    pass
if (month <= 3) or (month >= 9):    # Between march and september (winter)
    check_northern_lights(weather_df, notify_=False, print_message=True)