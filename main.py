import requests
from abc import ABC, abstractmethod
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from time import sleep
from variables import *

localtime = ZoneInfo(timezone)


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


class BaseNotifier(ABC):
    """Base class used for all notifications"""
    def __init__(self, notify_:bool=True, print_message:bool=True):
        self.notify_ = notify_
        self.print_message = print_message
        self.data = None
        self.data_poi = None # Data point of interest
        self.weather_df = None

    def base_headers(self, title:str, click:str, x_attach:str) -> dict:
        """Creates the header dictionary"""
        return {
            "Title": title,
            "Click": click,
            "Priority": notification_priority,
            "X-Attach": x_attach
        }

    def validate_response(self, response:requests.Response):
        """Checks if response is ok and sets self.data accordingly"""
        if response.ok:
            return response
        else:
            print("Response invalid, status code", response.status_code, self)
            return None
    
    def closest_weather_forecast(self) -> pd.DataFrame:
        """Returns a dataframe of a single row containing the closest weather forecast to the data_poi"""
        target_time_utc = self.data_poi["time_utc"]

        working_weather_df = self.weather_df.copy()
        working_weather_df["delta_time"] = working_weather_df["time_utc"].apply(lambda t: t-target_time_utc)
        working_weather_df["delta_time"] = working_weather_df["delta_time"].apply(lambda t: abs(t))
        working_weather_df = working_weather_df.sort_values(by="delta_time", key=abs)
        
        return working_weather_df.head(1)

    def append_weather(self, msg:str, weather_forecast:pd.DataFrame) -> str:
        """Returns the final message with a weather forecast at the end"""
        final_msg = msg

        delta_str = format_delta(weather_forecast["delta_time"].iloc[0])
        final_msg += f"\n\nHere is the closest weather forecast available ({delta_str}):\n"
        final_msg += f"Cloud coverage: {weather_forecast["cloud_area_fraction"].iloc[0]} %\n"
        final_msg += f"Wind speed: {weather_forecast["wind_speed"].iloc[0]} m/s"

        return final_msg

    def run(self, weather_df:pd.DataFrame) -> bool:
        """Fetches data and notifies of anything noteworthy"""
        self.weather_df = weather_df
        try:
            self.data = self.fetch_data()
        except Exception as e:
            print(e)
        if self.data is not None:
            self.data = self.parse_data()
            if self.is_notable():
                weather_forecast = self.closest_weather_forecast()
                msg = self.message()
                msg = self.append_weather(msg, weather_forecast)
                hdrs = self.headers()
                if self.print_message:
                    print(hdrs["Title"])
                    print(msg)
                if self.notify_:
                    return notify(msg, hdrs)
                return False
    
    @abstractmethod
    def fetch_data(self) -> requests.Response | None:
        """Get raw data from URL"""

    @abstractmethod
    def parse_data(self) -> pd.DataFrame:
        """Parse and clean data """

    @abstractmethod
    def is_notable(self) -> bool:
        """Decides if the event/data is worth notifying about, 
        if there is, it sets self.data_poi"""

    @abstractmethod
    def message(self) -> str:
        """Builds the notification message withouth the weather forecast"""
    
    @abstractmethod
    def headers(self) -> dict:
        """Builds the notification (ntfy) headers (Title, Click, Priority, X-Attach)"""


class NorthernLightsNotifier(BaseNotifier):
    def fetch_data(self):
        response = requests.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json")
        return self.validate_response(response)

    def parse_data(self) -> pd.DataFrame:
        data_json = self.data.json()
        forecast = []
        for data_point in data_json:
            if data_point["observed"] != "observed": # If datapoint is a prediction, not observation
                forecast.append({
                    "time_utc": to_datetime_utc(data_point["time_tag"]+"Z"),
                    "kp": data_point["kp"],
                    "noaa_scale": data_point["noaa_scale"]
                })
        
        return pd.DataFrame(forecast)

    def is_notable(self) -> bool:
        max_kp_row = self.data.loc[self.data["kp"].idxmax()]
        
        if max_kp_row["kp"] > kp_treshold:
            self.data_poi = max_kp_row
            return True
        self.data_poi = None
        return False

    def message(self) -> str:
        return f"Predictions show a chance of kp {self.data_poi['kp']} on {to_str_localtime(self.data_poi["time_utc"])}"
    
    def headers(self) -> dict:
        return self.base_headers(
            f"Chance for northern lights (kp {self.data_poi['kp']})",
            northern_lights_url,
            northern_lights_img_url
        )

class TransitNotifier(BaseNotifier):
    def fetch_data(self) -> requests.Response | None:
        response = requests.get(f"https://issinfo.net/api/transits-proxy?lat={latitude}&lon={longitude}&body=both&days=30&max_drive_km=50&visible_only=true")
        return self.validate_response(response)

    def parse_data(self) -> pd.DataFrame:
        data_json = self.data.json()

        #if data_json["count"] > 0:
        extracted_data = {
            "name": [],
            "body": [],
            "time_utc": []
        }
        for transit in data_json["transits"]:
            extracted_data["name"].append(transit["satellite_name"])
            extracted_data["body"].append(transit["body"])
            extracted_data["time_utc"].append(datetime.fromtimestamp(transit["utc_unix"], tz=ZoneInfo("UTC")))

        return pd.DataFrame(extracted_data)
    
    def is_notable(self) -> bool:
        # Transits always notify, so this will pick the first one if there is any
        self.data_poi = self.data.head(1)
        if self.data_poi.empty:
            return False
        return True
    
    def message(self) -> str:
        total_count = len(self.data)
        body = self.data_poi["body"].iloc[0]
        time_utc = self.data_poi["time_utc"].iloc[0]
        name = self.data_poi["name"].iloc[0]

        """
        Lunar transit (ISS)
        On Sunday, 12. July at 14:00 (2026) there will be an ISS lunar transit
        

        Multiple transits (ISS x2, Hubble x1)
        The first transit will happen on Sunday, 12. July at 14:00 (2026),
        this will be an ISS solar transit
        """

        transit_type = "solar"
        if body == "moon":
            transit_type = "lunar"
        if total_count == 1:
            return f"On {to_str_localtime(time_utc)} there will be a {transit_type} transit of {name}"
        else:
            return f"The first transit will occur on {to_str_localtime(time_utc)}, this will be a {transit_type} transit of {name}"

    def headers(self) -> dict:
        if self.data_poi["body"].iloc[0] == "moon":
            title = "Lunar transit"
            transit_img_url = lunar_transit_img_url
        else:
            title = "Solar transit"
            transit_img_url = solar_transit_img_url
        if len(self.data) > 1:
            title = "Multiple transits"
        transit_stations_str = ""
        station_count = self.data["name"].value_counts()
        for station in self.data["name"]:
            if station not in transit_stations_str:
                transit_stations_str += station+" x"+str(station_count[station])+", "
        title += " ("+transit_stations_str[:-2]+")"
        return self.base_headers(
            title,
            transit_url,
            transit_img_url
        )

class SunspotNotifier(BaseNotifier):
    def fetch_data(self) -> requests.Response | None:
        response = requests.get("https://services.swpc.noaa.gov/text/solar-regions.txt")
        return self.validate_response(response)

    def parse_data(self) -> pd.DataFrame:
        data_txt = self.data.text

        text_rows = data_txt.split("\n")

        data_rows = []
        for i, row in enumerate(text_rows): # Remove info, keep sunspot table
            if i > 11:
                data_rows.append(row.split(" "))
        
        clean_data_rows = [] # Remove blanks
        for i, row in enumerate(data_rows):
            clean_data_rows.append([])
            for d in row:
                if d != "":
                    clean_data_rows[i].append(d)
        clean_data_rows.remove([])

        today_utc_date = datetime.now(ZoneInfo("UTC")).date()
        target_time = time(hour=12, minute=0, second=0, tzinfo=ZoneInfo("UTC"))
        utc_today = datetime.combine(today_utc_date, target_time)
        final_data = []
        for row in clean_data_rows:
            final_data.append({
                "Area": int(row[3]),
                "Extent": int(row[4]),
                "Class": row[5],
                "Local count": int(row[6]),
                "time_utc": utc_today
            })
        
        return pd.DataFrame(final_data)

    def is_notable(self) -> bool:
        sum_area = sum(self.data["Area"])
        big_sunspot_count = sum(self.data["Area"] > 275)

        if sum_area > total_sunspot_area_treshold:
            self.data_poi = pd.DataFrame(
                {
                    "total_area": sum_area,
                    "big_sunspot_count": big_sunspot_count,
                    "time_utc": self.data["time_utc"][0]
                },
                index=[0]
            )
            return True
        else:
            self.data_poi = None
            return False

    def message(self) -> str:
        if self.data_poi["big_sunspot_count"].iloc[0] == 1:
            msg = f"There is {self.data_poi["big_sunspot_count"].iloc[0]} big sunspot on the sun, total area of all spots, {self.data_poi["total_area"].iloc[0]} MH"
        else:
            msg = f"There are {self.data_poi["big_sunspot_count"].iloc[0]} big sunspots on the sun, total area of all spots, {self.data_poi["total_area"].iloc[0]} MH"
        return msg

    def headers(self) -> dict:
        return self.base_headers(
            "Potentially multiple (big) sunspots",
            sun_url,
            sun_img_url
        )

class CometNotifier(BaseNotifier):
    def fetch_data(self) -> requests.Response | None:
        response = requests.get(f"https://cobs.si/data/planner/?session_date={datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d")}&sun_alt=0&name=Oslo&lat={latitude}&long={longitude}&elev={elevation}&tz=UTC&mag={comet_mag_treshold}&alt=10&sun_elong=0&moon_elong=0&filter=0&_=1783448627942")
        return self.validate_response(response)

    def parse_data(self) -> pd.DataFrame:
        return pd.DataFrame(self.data.json()["data"])

    def is_notable(self) -> bool:
        if len(self.data) > 0:
            self.data_poi = self.data.loc[self.data["magnitude"].idxmax()]
            self.data_poi["time_utc"] = to_datetime_utc(self.data_poi["best_time"]+"Z")
            return True
        self.data_poi = None
        return False
    
    def message(self) -> str:
        comet_mag = self.data_poi["magnitude"]
        best_viewing_time = self.data_poi["best_time"]
        comet_fullname = self.data_poi["comet_fullname"]
        altitude = self.data_poi["best_alt"]
        
        return f"Comet {comet_fullname} with a magnitude of {comet_mag} and altitude {altitude} will be the most visable at {best_viewing_time}"

    def headers(self) -> dict:
        if len(self.data) > 1:
            title = "Potentially multiple visable comets"
        else:
            title = "Potentially visable comet"
        return self.base_headers(
            title,
            f"{comet_url}{self.data_poi["comet_name"].lower()}-info",
            comet_img_url
        )


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
    latitude_short = round(float(latitude), 3)
    longitude_short = round(float(longitude), 3)

    #with open("weather.json", "r") as f:
    #    weather_forecast = json.load(f)

    weather_forecast = requests.get(f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={latitude_short}&lon={longitude_short}&altitude={elevation}")
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

def notify(message:str, headers:dict, tries:int=0, limit_tries:int=10) -> bool:
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


notifiers = {
    "northern_lights": NorthernLightsNotifier(),
    "transit": TransitNotifier(),
    "sunspot": SunspotNotifier(),
    "comet": CometNotifier()
}

weather_forecast = weather()
current_month = datetime.now().month
for notifier_type, notifier in notifiers.items():
    month_min = datetime.strptime(notification_info[notifier_type][0][0], "%b").month
    month_max = datetime.strptime(notification_info[notifier_type][0][1], "%b").month
    if month_min <= current_month <= month_max:
        if notification_info[notifier_type][1]:
            notifier.run(weather_forecast)
