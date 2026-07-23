import requests
import pandas as pd
import base64
from abc import ABC, abstractmethod
from functions import *

notification_priority = "3"

class BaseNotifier(ABC):
    """Base class used for all notifications"""
    def __init__(self, local_icon:str, notify_:bool=True, print_message:bool=False):
        self.notify_ = notify_
        self.print_message = print_message
        self.data = None
        self.data_poi = None # Data point of interest
        self.weather_df = None
        self.local_icon = local_icon

    def base_headers(self, title:str, click:str, x_attach:str) -> dict:
        """Creates the header dictionary"""
        if self.local_icon == "":
            return {
                "Title": title,
                "Click": click,
                "Priority": notification_priority,
                "X-Attach": x_attach
            }
        else:
            return {
                "Title": title,
                "Click": click,
                "Priority": notification_priority,
                #"X-Attach": x_attach,
                "X-Filename": self.local_icon+".png"
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
            print("Error in Base class method run()")
            print(e)
        if self.data is not None:
            self.data = self.parse_data()
            if self.is_notable():
                weather_forecast = self.closest_weather_forecast()
                msg = self.message()
                msg = self.append_weather(msg, weather_forecast)
                hdrs = self.headers()

                # Correct format for ntfy Message header
                message_bytes = msg.encode('utf-8')
                base64_bytes = base64.b64encode(message_bytes)
                base64_string = base64_bytes.decode('utf-8')
                encoded_header = f"=?UTF-8?B?{base64_string}?="

                hdrs["Message"] = encoded_header
                if self.print_message:
                    print(hdrs["Title"])
                    print(msg)
                if self.notify_:
                    return notify(msg, hdrs, self.local_icon)
                return False
    
    @abstractmethod
    def fetch_data(self):
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
