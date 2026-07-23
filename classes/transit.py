from .base import BaseNotifier
import requests
import pandas as pd
from transit_finder import find_iss_transits
from variables import *
from functions import *

transit_url = f"https://issinfo.net/transit-finder?lat={latitude}&lon={longitude}&days=30"
lunar_transit_img_url = "https://www.dropbox.com/scl/fi/grjasntzv3g5m4190wduc/lunar_transit.png?rlkey=cw26ju1xdxz9jucvufg4q2xhx&st=iv4om1ef&dl=1"
solar_transit_img_url = "https://www.dropbox.com/scl/fi/5hkcb42pi1gopd1a4hsah/solar_transit.png?rlkey=7i4hiq023y95gidz2l6k7r3bj&st=kuloh7hs&dl=1"

class TransitNotifier(BaseNotifier):
    def fetch_data(self) -> requests.Response | None:
        return find_iss_transits(float(latitude), float(longitude))

    def parse_data(self) -> pd.DataFrame:
        extracted_data = {
            "name": [],
            "body": [],
            "time_utc": [],
            "alt": [],
            "az": [],
            "best_lat": [],
            "best_lon": [],
            "obs_dist_km": []
        }
        for transit in self.data["transits"]:
            extracted_data["name"].append("ISS")
            extracted_data["body"].append(transit["body"])
            extracted_data["time_utc"].append(to_datetime_utc(transit["time_utc"]))
            extracted_data["alt"].append(transit["iss_alt"])
            extracted_data["az"].append(transit["iss_az"])
            extracted_data["best_lat"].append(transit["best_lat"])
            extracted_data["best_lon"].append(transit["best_lon"])
            extracted_data["obs_dist_km"].append(transit["obs_dist_km"])

        return pd.DataFrame(extracted_data)
    
    def is_notable(self) -> bool:
        # Transits always notify, so this will pick the first one if there are any
        if len(self.data) > 0:
            self.data_poi = self.data.iloc[0]
            if self.data_poi.empty:
                return False
            return True
        return False
    
    def message(self) -> str:
        total_count = len(self.data)
        body = self.data_poi["body"]
        time_utc = self.data_poi["time_utc"]
        name = self.data_poi["name"]
        alt, az = self.data_poi["alt"], self.data_poi["az"]

        if include_observation_horizon:
            if get_visibility(az, alt):
                visible_str = "The event will be visible from your observation point"
            else:
                visible_str = "The event will not be visible from your observation point"
        else:
            visible_str = ""

        transit_type = "solar"
        if body == "moon":
            transit_type = "lunar"
        if total_count == 1:
            return f"On {to_str_localtime(time_utc)} there will be a {transit_type} transit of {name}. {visible_str}"
        else:
            return f"The first transit will occur on {to_str_localtime(time_utc)}, this will be a {transit_type} transit of {name}. {visible_str}"

    def headers(self) -> dict:
        generate_horizon_img(self.data_poi["az"], self.data_poi["alt"], "transit")
        if self.data_poi["body"] == "moon":
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
