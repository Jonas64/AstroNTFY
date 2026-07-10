import requests
from datetime import datetime, date
from zoneinfo import ZoneInfo
import pandas
from time import sleep
from variables import topic, latitude, longitude, elevation, timezone

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

transit_url = f"https://issinfo.net/transit-finder?lat={latitude}&lon={longitude}&days=30"
northern_lights_url = "https://www.nordlysvarsel.com/en/"
sun_url = "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_2048_HMIIF.jpg"
comet_url = "https://theskylive.com/"

ntfy_url = f"https://ntfy.sh/{topic}"
notification_priority = "3"

kp_treshold = 5.5                   # If kp exceeds this value, you will be notified
total_sunspot_area_treshold = 1500  # If the total area of all sunspots exceeds this value, you will be notified
comet_mag_treshold = 10             # Any comet with a magnitude lower than this number will notify you

def convert_time(time_str_iso_8601_utc:str) -> tuple:
    dt_utc = datetime.fromisoformat(time_str_iso_8601_utc+"+00:00")

    # Convert to Oslo time zone
    date_str = dt_utc.astimezone(ZoneInfo(timezone))

    # Format to a readable local string including day
    formatted = (date_str.strftime("%Y-%m-%d %H:%M:%S %Z"), date_str.strftime("%A"))

    # Day and date
    date_final = ""
    date_final += formatted[1]+", " # Day
    date_str = formatted[0][8:10]+". " # Date
    if date_str[0] == "0":
        date_str = date_str[1:]
    date_final += date_str

    # Month
    date_final += translate_months[formatted[0][5:7]]

    # Time
    date_final += ", at "+formatted[0][11:16]

    return date_final

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

def check_northern_lights() -> dict:
    all_data = requests.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json")
    all_data = all_data.json()
    forecast = []
    for data_point in all_data:
        if data_point["observed"] != "observed": # If datapoint is a prediction, not observation
            time = convert_time(data_point["time_tag"])
            forecast.append({
                "time": time,
                "kp": data_point["kp"],
                "noaa_scale": data_point["noaa_scale"]
            })
    notify_northern_lights(forecast)

    return forecast

def notify_northern_lights(forecast:list):
    forecast_df = pandas.DataFrame(forecast)
    
    max_kp = max(forecast_df["kp"])
    max_kp_index = (forecast_df["kp"] == max_kp).idxmax() # Index for the max kp of all predictions
    if max_kp > kp_treshold:
        message = f"Predictions show a chance of kp {max_kp} on {forecast_df["time"][max_kp_index]}"
        
        headers = {
            "Title": f"Chance for northern lights (kp {max_kp})",
            "Click": northern_lights_url,
            "Priority": notification_priority
        }

        notify(message, headers)
    else:
        print("No northern light activity.")

def check_transits() -> dict:
    transits = requests.get(f"https://issinfo.net/api/transits-proxy?lat={latitude}&lon={longitude}&body=both&days=30&max_drive_km=50&visible_only=true")
    transits = transits.json()
    
    if transits["count"] > 0:
        all_satellite_names = []
        all_bodies = []
        for transit in transits["transits"]:
            all_satellite_names.append(transit["satellite_name"])
            all_bodies.append(transit["body"])

        notify_transit(transits["count"], all_satellite_names, all_bodies)

    return transits

def notify_transit(transit_count:int, transit_station:list, body:list):
    if body[0] == "moon":
        title = "Lunar transit"
    else:
        title = "Solar transit"
    if transit_count > 1:
        title = "Multiple transits"
    
    headers = {
        "Title": title,
        "Click": transit_url,
        "Priority": notification_priority
    }
    if transit_count == 1:
        message = title+f" ({transit_station[0]})"
    elif transit_count > 1:
        transit_stations_str = ", ".join(transit_station)
        message = title+f" ({transit_stations_str})"
    
    if transit_count > 0:
        notify(message, headers)
    else:
        print("No future transits.")

def remove_from_list(l:list, r) -> list:
    for row in l:
        while r in row:
            row.remove(r)
    return l

def check_solar_activity() -> dict:
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

    notify_solar_activity(final_data)
    
    return final_data

def notify_solar_activity(sunspots:dict):
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
            "Priority": notification_priority
        }

        notify(message, headers)
    else:
        print("No notable solar activity.")

def check_comets(date_to_check:str) -> dict:
    comet_data = requests.get(f"https://cobs.si/data/planner/?session_date={date_to_check}&sun_alt=0&name=Oslo&lat={latitude}&long={longitude}&elev={elevation}&tz=localtime&mag={comet_mag_treshold}&alt=0&sun_elong=0&moon_elong=0&filter=0&_=1783448627942")

    comet_data = comet_data.json()
    comet_data = comet_data["data"]

    if len(comet_data) > 0:
        notify_comets(comet_data)
    else:
        print("No notable bright/visable comets.")

def notify_comets(comets:dict):
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
        "Priority": notification_priority
    }
    
    notify(message, headers)


#transits = check_transits()
check_comets(date.today())

month = datetime.now().month
if (month >= 3) and (month <= 9):   # Between march and september (summer)
    #check_solar_activity()
    pass
if (month <= 3) or (month >= 9):    # Between march and september (winter)
    check_northern_lights()

#check_northern_lights()