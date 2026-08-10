from .base import BaseNotifier
import requests
import pandas as pd
from transit_finder import get_transit_dataframe
from variables import *
from functions import *

transit_url = f"https://issinfo.net/transit-finder?lat={latitude}&lon={longitude}&days=30"
lunar_transit_img_url = "https://www.dropbox.com/scl/fi/grjasntzv3g5m4190wduc/lunar_transit.png?rlkey=cw26ju1xdxz9jucvufg4q2xhx&st=iv4om1ef&dl=1"
solar_transit_img_url = "https://www.dropbox.com/scl/fi/5hkcb42pi1gopd1a4hsah/solar_transit.png?rlkey=7i4hiq023y95gidz2l6k7r3bj&st=kuloh7hs&dl=1"

class TransitNotifier(BaseNotifier):
    def fetch_data(self) -> requests.Response | None:
        return get_transit_dataframe(latitude, longitude, 50, 30)

    def parse_data(self) -> pd.DataFrame:
        return self.data
    
    def is_notable(self) -> bool:
        # Transits always notify, so this will pick the first one if there are any
        if len(self.data) > 0:
            self.data_poi = self.data.iloc[[0]].copy()
            if self.data_poi.empty:
                return False
            return True
        return False
    
    def message(self) -> str:
        total_count = len(self.data)
        body = self.data_poi["body"].iloc[0]
        time_utc = self.data_poi["time_utc"].iloc[0]
        name = self.data_poi["name"].iloc[0]
        alt, az = self.data_poi["iss_alt"].iloc[0], self.data_poi["iss_az"].iloc[0]

        if include_observation_horizon:
            horizon_imgs_visibility = get_visibility(az, alt)
            self.visible_from_horizon = horizon_imgs_visibility
            if horizon_imgs_visibility[0]:
                visible_str = "The event will be visible from "+horizon_imgs_visibility[1]
            else:
                visible_str = "The event will not be visible from any of your observation points"
        else:
            visible_str = ""

        transit_type = "solar"
        if body == "moon":
            transit_type = "lunar"
        if total_count == 1:
            return f"On {to_str_localtime(time_utc)} there will be a {transit_type} transit of {name} with a duration of {self.data_poi["duration"].iloc[0]} s. {visible_str}"
        else:
            return f"The first transit will occur on {to_str_localtime(time_utc)}, this will be a {transit_type} transit of {name} with a duration of {self.data_poi["duration"].iloc[0]} s. {visible_str}"

    def headers(self) -> dict:
        if include_observation_horizon and self.visible_from_horizon[0]:
            generate_horizon_img(self.data_poi["iss_az"].iloc[0], self.data_poi["iss_alt"].iloc[0], "transit", self.data_poi["time_utc"].iloc[0], self.data_poi["best_lat"].iloc[0], self.data_poi["best_lon"].iloc[0], self.visible_from_horizon[2][0])
        elif include_observation_horizon: # Not visible from any horizon, so pick the first one
            generate_horizon_img(self.data_poi["iss_az"].iloc[0], self.data_poi["iss_alt"].iloc[0], "transit", self.data_poi["time_utc"].iloc[0], self.data_poi["best_lat"].iloc[0], self.data_poi["best_lon"].iloc[0], list(horizon_imgs)[0])
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
