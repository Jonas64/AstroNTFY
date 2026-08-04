from .base import BaseNotifier
from skyfield.api import load, wgs84, Star
from skyfield import almanac
from skyfield.units import Angle
import pandas as pd
from variables import *
from functions import *

northern_lights_url = "https://www.nordlysvarsel.com/en/"
northern_lights_img_url = "https://www.dropbox.com/scl/fi/vfdq084syxys7b6n9jhmq/northern_lights.jpg?rlkey=pmo8l094bzjv1vn5cm5z10rf9&st=76hp8qps&dl=1"

ngc_type_translation = {
    "*":      "Star",
    "**":     "Double star",
    "*Ass":   "Association of stars",
    "OCl":    "Open Cluster",
    "GCl":    "Globular Cluster",
    "Cl+N":   "Star Cluster with Nebulosity",
    "G":      "Galaxy",
    "GPair":  "Galaxy Pair",
    "GTrpl":  "Galaxy Triplet",
    "GGroup": "Group of Galaxies",
    "PN":     "Planetary Nebula",
    "HII":    "HII Ionized Region",
    "EmN":    "Emission Nebula",
    "RfN":    "Reflection Nebula",
    "Neb":    "Nebula",
    "SNR":    "Supernova Remnant",
    "Nova":   "Nova Star",
    "DrkN":   "Dark Nebula",
    "NonEx":  "Nonexistent Object",
    "Dup":    "Duplicated Record",
    "Other":  "Other/Unclassified"
}

narrowband_suitability = {
    "Emission Nebula":                  {"Ha": 3, "OIII": 3, "SII": 3},
    "HII Ionized Region":               {"Ha": 3, "OIII": 1, "SII": 1},
    "Supernova Remnant":                {"Ha": 3, "OIII": 2, "SII": 3},
    "Planetary Nebula":                 {"Ha": 2, "OIII": 3, "SII": 1},
    "Nebula":                           {"Ha": 2, "OIII": 2, "SII": 2},
    "Star Cluster with Nebulosity":     {"Ha": 2, "OIII": 2, "SII": 1},
    "Reflection Nebula":                {"Ha": 0, "OIII": 0, "SII": 0},
    "Galaxy":                           {"Ha": 0, "OIII": 0, "SII": 0},
    "Galaxy Pair":                      {"Ha": 0, "OIII": 0, "SII": 0},
    "Galaxy Triplet":                   {"Ha": 0, "OIII": 0, "SII": 0},
    "Group of Galaxies":                {"Ha": 0, "OIII": 0, "SII": 0},
    "Association of stars":             {"Ha": 0, "OIII": 0, "SII": 0},
    "Dark Nebula":                      {"Ha": 0, "OIII": 0, "SII": 0}
}

check_for_time = datetime.now(tz=ZoneInfo("UTC")).replace(hour=21, minute=0, second=0, microsecond=0)

moon_phase = None
moon_alt, moon_az = None, None

class DeepSkyNotifier(BaseNotifier):
    def fetch_data(self) -> dict:
        with open("ngc.json", "r") as f:
            ngc = json.load(f)
        return ngc

    def parse_data(self) -> pd.DataFrame:
        self.data = pd.DataFrame(self.data)
        self.data["type"] = self.data["type"].apply(lambda type: ngc_type_translation[type])
        self.data["time_utc"] = check_for_time

        self.filter_objects()

        self.data_poi = self.data.iloc[0] # Placeholder for later (so get_closest_weather does not fail)

        return pd.DataFrame(self.data)

    def ra_dec_to_alt_az(self):
        global moon_phase, moon_alt, moon_az

        self.data = self.data.dropna(subset=["ra", "dec"])

        eph = load("de421.bsp")
        earth, moon, sun = eph['earth'], eph['moon'], eph['sun']

        ts = load.timescale()
        t = ts.from_datetime(check_for_time)

        observer = earth + wgs84.latlon(float(vb.latitude), float(vb.longitude))

        target = Star(ra=Angle(radians=self.data["ra"]), dec=Angle(radians=self.data["dec"]))

        astrometric = observer.at(t).observe(target)
        alt, az, distance = astrometric.apparent().altaz()

        self.data["alt"] = alt.degrees
        self.data["az"] = az.degrees

        fraction = earth.at(t).observe(moon).fraction_illuminated(sun)
        percent_illuminated = fraction * 100

        astrometric_moon = observer.at(t).observe(moon)
        moon_alt, moon_az, distance = astrometric_moon.apparent().altaz()
        moon_alt, moon_az = moon_alt.degrees, moon_alt.degrees

        moon_phase = percent_illuminated
    
    def clamp(self, value:float, min_:float, max_:float):
        return max(min(value, max_), min_)
    
    def effective_vmag(self, row:pd.Series):
        if pd.notna(row.loc["vmag"]):
            return row.loc["vmag"]
        if pd.notna(row.loc["bmag"]):
            return row.loc["bmag"] - 0.6
        return None  # no usable magnitude at all — drop or deprioritize this target

    def moon_proximity_score(self, target_alt, target_az):
        """
        Score based on angular distance between target and moon, scaled by
        how illuminated the moon is.

        target_alt, target_az: degrees

        Returns 0-1: low = target is close to a bright moon (bad),
                    high = target is far from the moon, or moon is dim (good).
        """
        moon_illumination = moon_phase/100
        # moon below horizon -> it can't be washing anything out, ignore proximity entirely
        if moon_alt < 0:
            return 1.0

        t_alt, t_az = math.radians(target_alt), math.radians(target_az)
        m_alt, m_az = math.radians(moon_alt), math.radians(moon_az)

        cos_sep = (math.sin(t_alt) * math.sin(m_alt) + math.cos(t_alt) * math.cos(m_alt) * math.cos(t_az - m_az))
        cos_sep = self.clamp(cos_sep, -1, 1)  # guard against float drift outside acos's domain
        separation_deg = math.degrees(math.acos(cos_sep))

        # 0 deg apart -> 0 (bad), 180 deg apart -> 1 (good)
        separation_score = separation_deg / 180

        # dim moon: proximity barely matters, score stays near 1 regardless of separation
        # bright moon: proximity fully matters, score reduces toward separation_score
        score = 1 - (1 - separation_score) * moon_illumination
        return self.clamp(score, 0, 1)
    
    def score_target(self, target: pd.Series, vmag_min: float, vmag_max: float, ideal_fill: float = 0.6):
        weights = {"narrowband": 0.5, "alt": 0.35, "brightness": 0.15, "framing": 0.1, "moon": 0.25, "surf_brightness": 0.15, "moon_prox": 0.25}
        all_scores = []

        if target.loc["type"] in ["Planetary Nebula", "HII Ionized Region", "Emission Nebula", "Nebula", "Supernova Remnant", "Star Cluster with Nebulosity"]: # Narrowband score
            bortle_norm = self.clamp(bortle_scale / 9, 0, 1)
            filter_score = 0
            for filter in rig_config["filters"]: # Weigh narrowband score based on what filters the user has available
                if target.loc["type"] in list(narrowband_suitability):
                    filter_score += narrowband_suitability[target.loc["type"]][filter]
            filter_score = filter_score/9

            all_scores.append(translate(bortle_norm, 0, 1, 0.5, 1) * weights["narrowband"] * filter_score)
        else:
            all_scores.append(0)

        all_scores.append(translate(target.loc["alt"], 25, 90, 0, 1) * weights["alt"]) # Target altitude score
        if target.loc["type"] == "Reflection Nebula": # Moon phase score
            all_scores.append(self.clamp((((moon_phase / 122.475) ** 2) * 1.5) + 0.4, 0, 1) * weights["moon"])
        else:
            all_scores.append(self.clamp(((moon_phase / 122.475) ** 2) * 1.5, 0, 1) * weights["moon"])

        frame_penalty = self.clamp(abs(target.loc["fill_ratio"] - ideal_fill), 0, 1)
        all_scores.append((1 - frame_penalty) * weights["framing"]) # Framing score

        vmag_range = vmag_max - vmag_min
        brightness_norm = self.clamp((target.loc["eff_vmag"] - vmag_min) / (vmag_range + 1e-9), 0, 1)
        all_scores.append((1 - brightness_norm) * weights["brightness"]) # Magnitude score

        all_scores.append(self.clamp(1 - (target.loc["sbrightn"] - SQM) / (22.5 - SQM), 0, 1) * weights["surf_brightness"]) # Surface brightness score

        all_scores.append(self.moon_proximity_score(target.loc["alt"], target.loc["az"]) * weights["moon_prox"]) # Moon proximity score, how close is moon to target

        new_scores = [] # Remove NaN (some object dont have magnitude, surface brightness etc.)
        for score in all_scores:
            if not pd.isna(score):
                new_scores.append(score)

        return sum(new_scores)
    
    def filter_objects(self):
        self.ra_dec_to_alt_az()
        self.data = self.data[self.data["alt"] >= 25] # Exclude targets that are too close to horizon

        self.data["visible"] = get_visibility_df(self.data["az"], self.data["alt"]) # Check visibility

        self.data = self.data[self.data["visible"] != False] # Drop all object that are not visible

        fov_long = max(fov_rig_x, fov_rig_y)
        fov_short = min(fov_rig_x, fov_rig_y)

        self.data["fill_ratio"] = self.data["majax"] / fov_short   # fraction of the short axis it spans
        self.data["fits_frame"] = self.data["majax"] <= fov_long   # still fits at all, even oriented favorably

        MIN_FILL = 0.30   # object should span at least ~30% of the frame's short axis
        MAX_FILL = 1.5    # allow a little crop past the short axis before calling it "too large"

        self.data["too_small"] = self.data["fill_ratio"] < MIN_FILL
        self.data["too_large"] = (~self.data["fits_frame"]) | (self.data["fill_ratio"] > MAX_FILL)
        self.data["good_fit"]  = ~self.data["too_small"] & ~self.data["too_large"]

        self.data = self.data[self.data["good_fit"] != False]

        self.data["eff_vmag"] = self.data.apply(self.effective_vmag, axis=1) # Get brightness

        vmin, vmax = self.data["eff_vmag"].min(), self.data["eff_vmag"].max()
        self.data["total_score"] = self.data.apply(lambda row: self.score_target(row, vmin, vmax), axis=1)
        self.data.sort_values(by="total_score", inplace=True)
    
    def is_notable(self) -> bool:
        if self.data_poi["closest_weather"]["cloud_area_fraction"].iloc[0] > 15:
            return False
        top_scores = self.data.tail(10)
        weights = np.exp(top_scores["total_score"] * 5)  # tune the multiplier: higher = more winner-take-all
        probs = weights / weights.sum()
        random_target = top_scores.sample(n=1, weights=probs).iloc[0]
        
        if not random_target.empty:
            self.data_poi = random_target
            return True
        self.data_poi = None
        return False

    def message(self) -> str:
        if include_observation_horizon:
            horizon_imgs_visibility = get_visibility(self.data_poi["az"], self.data_poi["alt"])
            self.visible_from_horizon = horizon_imgs_visibility

        if self.data_poi["commonnames"] != "":
            names = self.data_poi["commonnames"].split(",")
            name = names[0]
        else:
            name = self.data_poi["name"]
        self.data_poi["clean_name"] = name

        return f"Based on multiple factors, {name} is ideally placed for photography tonight. "

    def headers(self) -> dict:
        if include_observation_horizon:
            generate_telescope_view(math.degrees(self.data_poi["ra"]), math.degrees(self.data_poi["dec"]))
        return self.base_headers(
            f"{self.data_poi["clean_name"]} will be an ideal candidate for astrophotography tonight",
            northern_lights_url,
            northern_lights_img_url
        )
