topic = "xxxx"                      # Your topic
latitude = "52.52"                  # Your latitude
longitude = "13.405"                # Your longitude
elevation = "100"                   # Your altitude in meters above sea level
timezone = "Europe/Berlin"          # The timezone of where you will be observing from (IANA Time Zone Database)

kp_treshold = 6                     # If kp exceeds this value, you will be notified
total_sunspot_area_treshold = 1500  # If the total area (measured in MH) of all sunspots exceeds this value, you will be notified
comet_mag_treshold = 7              # Any comet with a magnitude lower than this number will notify you

# ((from month, to month), should this event notify you(True/False))
# ("Jan", "Dec") will notify you the whole year
notification_info = {
    "northern_lights": (("Sep", "Apr"), True),
    "transit": (("Jan", "Dec"), True),
    "sunspot": (("Mar", "Sep"), True),
    "comet": (("Aug", "Apr"), True)
}

""" Prints all available timezones
import zoneinfo
timezones = sorted(zoneinfo.available_timezones())
for t in timezones:
    print(t)
"""