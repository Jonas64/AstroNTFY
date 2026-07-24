from datetime import datetime
from zoneinfo import ZoneInfo

from classes import *
from variables import *
from functions import *

localtime = ZoneInfo(timezone)

notifiers = {
    "northern_lights": NorthernLightsNotifier(""),
    "transit": TransitNotifier("transit"),
    "sunspot": SunspotNotifier(""),
    "comet": CometNotifier("comet")
}

weather_forecast = pd.DataFrame()
current_month = datetime.now().month
for notifier_type, notifier in notifiers.items():
    month_min = datetime.strptime(notification_info[notifier_type][0][0], "%b").month
    month_max = datetime.strptime(notification_info[notifier_type][0][1], "%b").month
    if month_min <= current_month <= month_max:
        if notification_info[notifier_type][1]:
            if weather_forecast.empty:
                weather_forecast = weather()
            notifier.run(weather_forecast)
