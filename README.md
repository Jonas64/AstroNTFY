# AstroNTFY
Notifies you through the NTFY app of astronomical events. 

## Features
The current version has implemented notifications for:
1. Northern lights
2. ISS solar/lunar transits
3. Many/big sunspots
4. Comets

Every notification also includes the closest available weather forecast (cloud coverage and wind speed) to the relevant date and time.

You can also include a sentence in the relevant notifications about whether or not any obstacles at yout observation point will block the event. More info on how this is done [below](#Observation-point-horizon).

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

## Observation point horizon
To be sure that the event (for example an ISS lunar transit) is visible from your observation point, you can add your own 360 degree equirectangular image. I have added an example image in the [obs_horizon](obs_horizon) folder. 

You can capture such an image using any phone with apps like 360 Photo Cam on iOS. These apps usually offer at least one free download. 

After downloading the image you need to make the sky transparent using any photo editing software. Now replace the example photo with your horizon, make sure it is a png, the resolution does not matter. 