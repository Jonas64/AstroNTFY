# AstroNTFY
Notifies you through the NTFY app of astronomical events. 

## Features
The current version has implemented notifications for:
1. Northern lights
2. Satellite solar/lunar transits
3. Many/big sunspots
4. Comets

Every notification also includes the closest available weather forecast (cloud coverage and wind speed) for the relevant date and time.

## Installation
Setup a virtual environment.
```sh
virtualenv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

## Setup ntfy.sh app
In order for you to recieve notifications, you will need the [ntfy.sh](https://ntfy.sh/) app. Download this on the device(s) that will be recieving notifications.

Create a new topic in the app with a cryptic name that people wont guess. I used a password generator.

## Final setup
Finally, fill in the variables in [variables_example.py](variables_example.py) and rename it to variables.py.