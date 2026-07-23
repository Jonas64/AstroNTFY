topic = "xxxx"                      # Your topic
latitude = "52.5200"                # Your latitude
longitude = "13.4050"               # Your longitude
elevation = "38"                    # Your altitude in meters above sea level
timezone = "Europe/Berlin"          # The timezone of where you will be observing from (IANA Time Zone Database)

kp_treshold = 6                     # If kp exceeds this value, you will be notified
total_sunspot_area_treshold = 1500  # If the total area (measured in MH) of all sunspots exceeds this value, you will be notified
comet_mag_treshold = 7              # Any comet with a magnitude lower than this number will notify you

include_observation_horizon = False # Leave this False if you will not be adding your own horizon.png image, else change to True
horizon_north_offset = 0            # How many degrees offset is your image from true north (-360 to +360)

# ((from month, to month), should this event notify you? (True/False))
# E.g. ("Jan", "Dec") will notify you the whole year
notification_info = {
    "northern_lights":  (("Sep", "Apr"), True),
    "transit":          (("Jan", "Dec"), True),
    "sunspot":          (("Mar", "Sep"), True),
    "comet":            (("Aug", "Apr"), True)
}

""" Prints all available timezones
import zoneinfo
timezones = sorted(zoneinfo.available_timezones())
for t in timezones:
    print(t)
"""