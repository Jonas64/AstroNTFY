from .base import BaseNotifier
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from variables import *
from functions import *

comet_url = "https://theskylive.com/"
comet_img_url = "https://www.dropbox.com/scl/fi/06p5j4foc4j72t2hxepe1/comet.jpg?rlkey=ssmvrl1sd1b7atub3v6dx70g3&st=jz64u6cp&dl=1"

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
        best_viewing_time = to_str_localtime(self.data_poi["time_utc"])
        comet_fullname = self.data_poi["comet_fullname"]
        altitude = self.data_poi["best_alt"]

        if include_observation_horizon:
            _alt, azimuth = ra_dec_to_alt_az(self.data_poi["best_ra_float"], self.data_poi["best_dec"])
            self.data_poi["best_az"] = azimuth
            if get_visibility(azimuth, altitude):
                visible_str = "\nAt it's maximum altitude, the comet will be visible from your observation point"
            else:
                visible_str = "\nAt it's maximum altitude, the comet will not be visible from your observation point due to obstacles"
        else:
            visible_str = ""
        
        return f"Comet {comet_fullname} with a magnitude of {comet_mag} and a maximum altitude of {altitude} will be the most visable at {best_viewing_time}. {visible_str}"

    def headers(self) -> dict:
        generate_horizon_img(self.data_poi["best_az"], self.data_poi["best_alt"], "comet", self.data_poi["time_utc"])
        if len(self.data) > 1:
            title = "Potentially multiple visable comets"
        else:
            title = "Potentially visable comet"
        return self.base_headers(
            title,
            f"{comet_url}{self.data_poi["comet_name"].lower()}-info",
            comet_img_url
        )
