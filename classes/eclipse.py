from .base import BaseNotifier
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from variables import *
from functions import *

eclipse_url = "https://www.timeanddate.com/eclipse/in/"
eclipse_img_url = "https://www.dropbox.com/scl/fi/7e8ccet0dlf9j7tfeew6q/eclipse.jpeg?rlkey=4e1dscs94cnvjk590ilc1d4ge&st=08u5hqf6&dl=1"

class EclipseNotifier(BaseNotifier):
    def fetch_data(self) -> dict | None:
        """
        Fetches raw data for solar and lunar eclipse
        Returns a bundled dict on success, or None if any critical API fails.
        """

        year = datetime.now().year

        # Solar eclipse request
        solar_response = requests.get(f"https://opale.imcce.fr/api/v1/phenomena/eclipses/10/{year}?observer={latitude},{longitude},{elevation}&nbd=2")
        if self.validate_response(solar_response) is None:
            return None
        
        # Lunar eclipse request
        lunar_response = requests.get(f"https://opale.imcce.fr/api/v1/phenomena/eclipses/301/{year}?nbd=2")
        if self.validate_response(lunar_response) is None:
            return None

        return {
            "solar": solar_response,
            "lunar": lunar_response
        }
    
    def parse_lunar_data(self) -> list:
        lunar_data = self.data["lunar"].json()["response"]["lunareclipse"]
        lunar_events = []

        for eclipse in lunar_data:
            local_data = calculate_local_lunar_eclipse(
                to_datetime_utc(eclipse["events"]["P1"]["date"]),
                to_datetime_utc(eclipse["events"]["greatest"]["date"]),
                to_datetime_utc(eclipse["events"]["P2"]["date"]),
                eclipse["magnitude"]
            )
            lunar_events.append(
                {
                    "body": "moon",
                    "type": eclipse["type"].replace("Eclipse", "").lower(),

                    "begin_utc": local_data["global_times_utc"]["begins_P1"],
                    "maximum_utc": local_data["global_times_utc"]["greatest"],
                    "end_utc": local_data["global_times_utc"]["ends_P2"],

                    "obscuration": None,
                    "magnitude": local_data["magnitude"],

                    "begin_alt": local_data["local_positions"]["at_start"]["alt"],
                    "begin_az": local_data["local_positions"]["at_start"]["az"],

                    "maximum_az": local_data["highest_position_in_sky"]["azimuth"],
                    "maximum_alt": local_data["highest_position_in_sky"]["altitude"],

                    "end_alt": local_data["local_positions"]["at_end"]["alt"],
                    "end_az": local_data["local_positions"]["at_end"]["az"],

                    "visible": local_data["highest_position_in_sky"]["altitude"] > 0,
                    "begin_visible": local_data["local_positions"]["at_start"]["alt"] > 0,
                    "max_visible": local_data["local_positions"]["at_greatest"]["alt"] > 0,
                    "end_visible": local_data["local_positions"]["at_end"]["alt"] > 0
                }
            )

        return lunar_events

    def parse_solar_data(self) -> list:
        solar_data = self.data["solar"].json()["response"]["data"]
        solar_events = []

        for eclipse in solar_data:
            begin_alt = eclipse["events"]["P1"]["Sun"]["elevation"]
            maximum_alt = eclipse["events"]["greatest"]["Sun"]["elevation"]
            end_alt = eclipse["events"]["P4"]["Sun"]["elevation"]
            solar_events.append(
                {
                    "body": "sun",
                    "type": eclipse["type"].replace("Observer", "").replace("Eclipse", "").lower(),

                    "begin_utc": to_datetime_utc(eclipse["events"]["P1"]["date"]),
                    "maximum_utc": to_datetime_utc(eclipse["events"]["greatest"]["date"]),
                    "end_utc": to_datetime_utc(eclipse["events"]["P4"]["date"]),

                    "obscuration": eclipse["obscuration"],
                    "magnitude": eclipse["magnitude"],

                    "begin_az": eclipse["events"]["P1"]["Sun"]["azimuth"],
                    "begin_alt": eclipse["events"]["P1"]["Sun"]["elevation"],

                    "maximum_az": eclipse["events"]["greatest"]["Sun"]["azimuth"],
                    "maximum_alt": eclipse["events"]["greatest"]["Sun"]["elevation"],

                    "end_az": eclipse["events"]["P4"]["Sun"]["azimuth"],
                    "end_alt": eclipse["events"]["P4"]["Sun"]["elevation"],

                    "visible": (begin_alt > 0) or (maximum_alt > 0) or (end_alt > 0),
                    "begin_visible": begin_alt > 0,
                    "max_visible": maximum_alt > 0,
                    "end_visible": end_alt > 0
                }
            )
        
        return solar_events

    def parse_data(self) -> pd.DataFrame:
        data_list = self.parse_solar_data()+self.parse_lunar_data()

        return pd.DataFrame(data_list)

    def is_notable(self) -> bool:
        if len(self.data) > 0:
            self.data.drop(self.data[self.data["visible"] == False].index, inplace=True)
            sorted_by_time = self.data.sort_values(by="maximum_utc")
            self.data_poi = sorted_by_time.iloc[[0]].copy()
            self.data_poi["time_utc"] = self.data_poi["maximum_utc"].iloc[0]
            if ((self.data_poi["maximum_utc"].iloc[0]-datetime.now(tz=ZoneInfo("UTC"))).days > days_in_advance) or not self.data_poi["visible"].iloc[0]:
                self.data_poi = None
                return False
            return True
        self.data_poi = None
        return False
    
    def message(self) -> str:
        eclipse_type = self.data_poi["type"].iloc[0]
        body = self.data_poi["body"].iloc[0]
        max_local = to_str_localtime(self.data_poi["maximum_utc"].iloc[0])
        max_alt = self.data_poi["maximum_alt"].iloc[0]
        max_visible = self.data_poi["max_visible"].iloc[0]
        begin_visible = self.data_poi["begin_visible"].iloc[0]
        end_visible = self.data_poi["end_visible"].iloc[0]
        magnitude = self.data_poi["magnitude"].iloc[0]
        
        if body == "sun":
            body_str = "solar"
        else:
            body_str = "lunar"

        if include_observation_horizon:
            horizon_imgs_visibility_max = get_visibility(self.data_poi["maximum_az"].iloc[0], self.data_poi["maximum_alt"].iloc[0])
            horizon_imgs_visibility_begin = get_visibility(self.data_poi["begin_az"].iloc[0], self.data_poi["begin_alt"].iloc[0])
            horizon_imgs_visibility_end = get_visibility(self.data_poi["end_az"].iloc[0], self.data_poi["end_alt"].iloc[0])
            if horizon_imgs_visibility_max[0] and max_visible:
                visible_str = "\nAt the eclipse's maximum, it will be visible from "+horizon_imgs_visibility_max[1]
                self.visible_from_horizon = horizon_imgs_visibility_max
            elif horizon_imgs_visibility_begin[0] and begin_visible:
                visible_str = f"\nThe eclipse will be visible at the start of the event from {horizon_imgs_visibility_begin[1]}, however you will not see the maximum of the eclipse due to obstacles"
                self.visible_from_horizon = horizon_imgs_visibility_begin
            elif horizon_imgs_visibility_end[0] and end_visible:
                visible_str = f"\nThe eclipse will be visible towards the end of the event from {horizon_imgs_visibility_end[1]}, however you will not see the maximum of the eclipse due to obstacles"
                self.visible_from_horizon = horizon_imgs_visibility_end
            else:
                visible_str = "\nThe eclipse will not at all be visible from any of your observation points due to obstacles. "
                self.visible_from_horizon = horizon_imgs_visibility_max
        else:
            visible_str = ""

        msg = f"There will be a {eclipse_type.capitalize()} {body_str} eclipse on {max_local}. The magnitude of the eclipse is {round(magnitude, 2)}. At the greatest eclipse (from you location) the {body} will be at an altitude of {round(max_alt, 1)}°. "

        if body == "sun":
            obscuration = str(self.data_poi["obscuration"].iloc[0])
            msg += f"{obscuration} % of the sun will be covered. "
        
        return msg+visible_str

    def headers(self) -> dict:
        if include_observation_horizon and self.visible_from_horizon[0]:
            best_alt, best_az = 0, 0
            best_time = None
            if self.data_poi["max_visible"].iloc[0]:
                best_alt, best_az = self.data_poi["maximum_alt"].iloc[0], self.data_poi["maximum_az"].iloc[0]
                best_time = self.data_poi["maximum_utc"].iloc[0]
            elif self.data_poi["begin_visible"].iloc[0]:
                best_alt, best_az = self.data_poi["begin_alt"].iloc[0], self.data_poi["begin_az"].iloc[0]
                best_time = self.data_poi["begin_utc"].iloc[0]
            else:
                best_alt, best_az = self.data_poi["end_alt"].iloc[0], self.data_poi["end_az"].iloc[0]
                best_time = self.data_poi["end_utc"].iloc[0]
            generate_horizon_img(best_az, best_alt, "eclipse", best_time, float(latitude), float(longitude), self.visible_from_horizon[2][0])
        
        if self.data_poi["body"].iloc[0] == "sun":
            body_str = "solar"
        else:
            body_str = "lunar"

        return self.base_headers(
            f"{self.data_poi["type"].iloc[0].capitalize()} {body_str} eclipse",
            eclipse_url,
            eclipse_img_url
        )
