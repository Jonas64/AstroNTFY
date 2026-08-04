# AstroNTFY
Notifies you through the NTFY app of astronomical events. 

## Features
The current version has implemented notifications for:
1. Northern lights
2. ISS solar/lunar transits
3. Many/big sunspots
4. Comets
5. Lunar/solar eclipses
6. Good candidates for deep sky astrophotography every clear day (entire NGC and IC catalogs)

Every notification also includes the closest available weather forecast (cloud coverage and wind speed) to the relevant date and time.

You can also include a sentence in the relevant notifications about whether or not any obstacles at your observation point will block the event as well as an image of your sky showing where the transit, comet or eclipse will be. More info on how this is done and what the result looks like [below](#Observation-point-horizon).

# Minimal setup

## Installation
Setup a virtual environment.
```sh
virtualenv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

## Setup ntfy.sh app
In order for you to receive notifications, you will need the [ntfy.sh](https://ntfy.sh/) app. Download this on the device(s) that will be receiving notifications.

Create a new topic in the app with a cryptic name that people won't guess. I used a password generator.

## Final setup
Finally, fill in the variables (latitude/longitude, elevation, ntfy topic, timezone) in [variables_example.py](variables_example.py) and rename it to variables.py.

If you just want to use the program without downloading anything, keep the deep_sky False in notification_info. More on this [below](#download-sky-survey)

There are also other variables for more control over the notifications, that is documented [there](variables_example.py).

## Running the program
Currently, you need to run the [main.py](main.py) file to check for all events and notify. You could for example have it run once every day using you operating systems task scheduler. 

# Optional
## Deep sky notificaitons
The deep sky notifier calculates what targets are good candidates for astrophotography tonight based on

1. Target altitude
2. Target magnitude
3. Target surface brightness
4. Narrowband suitability (if you have any filters in your [rig_config](variables_example.py))
5. Moon position
6. Framing based on [rig_config](variables_example.py) (focal length, sensor size)

If you are using horizon images as well, the program will only give you targets that are visible from at least one of the observation points. 

Here is an example of an image you might recieve

![Deep sky example notification](readme_imgs/deep_sky_notification_example.png)

### Download sky survey
For the deep sky notifier, you need to donwload the [sky survey from noirlab](https://noirlab.edu/public/images/noirlab2430b/). If your focal length is over 300mm, I recommend downloading the [Large JPEG](https://storage.noirlab.edu/media/archives/images/large/noirlab2430b.jpg). If you have anything less or would rather have a smaller file, use the [Publication JPEG](https://storage.noirlab.edu/media/archives/images/publicationjpg/noirlab2430b.jpg). Place the downloaded image in the same folder as [main.py](main.py)

As mentioned above, if you don't want to download anything, just skip this step and change the [variables file](variables_example.py) so you won't get any notifications about deep sky objects. 

## Observation point horizon
To be sure that the event (for example an ISS lunar transit) is visible from your observation point, you can add your own 360 degree equirectangular image. You can have multiple horizon images in this folder, just keep in mind they are all using the same location (latitude, longitude). I have added an [example image](obs_horizon/horizon_example.png) in the obs_horizon folder:

![Horizon example](obs_horizon/horizon_example.png)

### Capturing the image
You can capture such an image using any phone with apps like 360 Photo Cam on iOS. These apps usually offer at least one free download. 

After downloading the image you need to make the sky transparent using any photo editing software. Now replace the example photo with your horizon, make sure it is a png, the resolution does not matter and rename it to horizon.png. 

### Calculating north offset
The final step is to line up the image to true north. This is a bit tricky, but try to find a landmark at your observation point that you can find easily in your 360 image. 

Check the angle of this landmark in the image using Stellarium, or the formula below:

1. $Az$ = azimuth
2. $x$ = x value of pixel
3. $width$ = x resolution of image

$Az=(\frac{x}{width})\times360$

Find the real azimuth for the landmark by standing exactly where you took the photo and use the compass app on your phone. 

Now subtract the two and you're left with the horizon_north_offset variable that you set in [variables_example.py](variables_example.py).

There are many ways to do this of course, some are probably easier and more precise. This is only a suggestion.

### Result
Here is an example image you might receive with a notification showing where a comet will be in your sky with your horizon image as a foreground.

![Notification example](readme_imgs/comet_notification_example.png)