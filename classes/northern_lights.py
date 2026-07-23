from .base import BaseNotifier
import requests
import pandas as pd
from variables import *
from functions import *

northern_lights_url = "https://www.nordlysvarsel.com/en/"
northern_lights_img_url = "https://www.dropbox.com/scl/fi/vfdq084syxys7b6n9jhmq/northern_lights.jpg?rlkey=pmo8l094bzjv1vn5cm5z10rf9&st=76hp8qps&dl=1"

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
