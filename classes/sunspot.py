from .base import BaseNotifier
import requests
import pandas as pd
from datetime import datetime, time
from zoneinfo import ZoneInfo
from variables import *

sun_url = "https://sdo.gsfc.nasa.gov/assets/img/latest/latest_2048_HMIIF.jpg"
sun_img_url = "https://www.dropbox.com/scl/fi/f0uw2qs5th3hnx2bbm2ix/sun.jpg?rlkey=pjzfahajf2yy9fewhd5yztp7q&st=38qhs911&dl=1"

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
            self.data_poi = pd.Series({
                "total_area": sum_area,
                "big_sunspot_count": big_sunspot_count,
                "time_utc": self.data["time_utc"].iloc[0]
            })
            return True
        else:
            self.data_poi = None
            return False

    def message(self) -> str:
        if self.data_poi["big_sunspot_count"] == 1:
            msg = f"There is {self.data_poi["big_sunspot_count"]} big sunspot on the sun, total area of all spots, {self.data_poi["total_area"]} MH"
        else:
            msg = f"There are {self.data_poi["big_sunspot_count"]} big sunspots on the sun, total area of all spots, {self.data_poi["total_area"]} MH"
        return msg

    def headers(self) -> dict:
        return self.base_headers(
            "Potentially multiple (big) sunspots today",
            sun_url,
            sun_img_url
        )
