import pandas as pd
from datetime import datetime
import classes as c
import variables as vb
import functions as fn

from pathlib import Path

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

weather_forecast = pd.DataFrame()
current_month = datetime.now().month
for notifier_type, notifier in notifiers.items():
    month_min = datetime.strptime(vb.notification_info[notifier_type][0][0], "%b").month
    month_max = datetime.strptime(vb.notification_info[notifier_type][0][1], "%b").month
    if month_min <= month_max:
        in_season = month_min <= current_month <= month_max
    else:
        in_season = current_month >= month_min or current_month <= month_max
    if in_season:
        if vb.notification_info[notifier_type][1]:
            if weather_forecast.empty:
                weather_forecast = fn.weather()
            notifier.run(weather_forecast)
