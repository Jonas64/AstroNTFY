import pandas as pd
from datetime import datetime
import classes as c
import variables as vb
import functions as fn

from pathlib import Path

def get_in_season(notifier_type:str, current_month:int) -> bool:
    month_min = datetime.strptime(vb.notification_info[notifier_type][0][0], "%b").month
    month_max = datetime.strptime(vb.notification_info[notifier_type][0][1], "%b").month
    if month_min <= month_max:
        in_season = month_min <= current_month <= month_max
    else:
        in_season = current_month >= month_min or current_month <= month_max

    return in_season

icon_dir = Path("icons")
icon_dir.mkdir(exist_ok=True)

notifiers = {
    "northern_lights": c.NorthernLightsNotifier(""),
    "transit": c.TransitNotifier("transit"),
    "sunspot": c.SunspotNotifier(""),
    "comet": c.CometNotifier("comet"),
    "eclipse": c.EclipseNotifier("eclipse"),
    "deep_sky": c.DeepSkyNotifier("DSO")
}

current_month = datetime.now().month

ran_notifiers = []
for n in notifiers:
    if get_in_season(n, current_month):
        ran_notifiers.append(n)

if len(ran_notifiers) > 0:
    log_txt = f"{datetime.now(tz=vb.localtime)} | Ran notifiers {", ".join(ran_notifiers)}."
else:
    log_txt = f"{datetime.now(tz=vb.localtime)} | No notifiers ran."

print(log_txt)

weather_forecast = pd.DataFrame()
for notifier_type, notifier in notifiers.items():
    if get_in_season(notifier_type, current_month):
        if vb.notification_info[notifier_type][1]:
            if weather_forecast.empty:
                weather_forecast = fn.weather()
            notifier.run(weather_forecast)
