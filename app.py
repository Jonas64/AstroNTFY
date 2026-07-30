import zoneinfo
from flask import Flask, request, render_template_string, flash, redirect, url_for

app = Flask(__name__)
app.secret_key = "astronomy_configurator_key"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Default values if variables.py does not exist yet
DEFAULT_CONFIG = {
    "topic": "My Topic",
    "latitude": "52.5200",
    "longitude": "13.4050",
    "elevation": "38",
    "local_timezone": "Europe/Berlin",
    "kp_treshold": 6,
    "total_sunspot_area_treshold": 1500,
    "comet_mag_treshold": 7,
    "include_observation_horizon": False,
    "horizon_north_offset": 0,
    "redirect_to_website": False,
    "days_in_advance": 30,
    "notification_info": {
        "northern_lights": (("Jan", "Dec"), True),
        "transit": (("Jan", "Dec"), True),
        "sunspot": (("Jan", "Dec"), True),
        "comet": (("Jan", "Dec"), True),
        "eclipse": (("Jan", "Dec"), True),
    }
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Notifier Settings Configurator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #e2e8f0; font-family: system-ui, -apple-system, sans-serif; }
        .card { border-radius: 12px; border: 1px solid #334155; background-color: #1e293b; color: #f8fafc; margin-bottom: 1.5rem; }
        .card-header-required { background-color: #2563eb; color: #ffffff; border-radius: 12px 12px 0 0 !important; font-weight: 700; }
        .card-header-optional { background-color: #334155; color: #ffffff; border-radius: 12px 12px 0 0 !important; font-weight: 700; }
        .badge-req { background-color: #dc2626; font-size: 0.75rem; vertical-align: middle; }
        .badge-opt { background-color: #64748b; font-size: 0.75rem; vertical-align: middle; }
        .form-label { font-weight: 600; font-size: 0.9rem; color: #cbd5e1; }
        .form-control, .form-select { background-color: #0f172a; border: 1px solid #475569; color: #f8fafc; }
        .form-control:focus, .form-select:focus { background-color: #0f172a; border-color: #3b82f6; color: #ffffff; box-shadow: 0 0 0 0.25rem rgba(59, 130, 246, 0.25); }
        .help-text { font-size: 0.8rem; color: #94a3b8; }
        .btn-save { background-color: #2563eb; color: #ffffff; padding: 12px 32px; font-weight: 600; border-radius: 8px; font-size: 1.05rem; }
        .btn-save:hover { background-color: #1d4ed8; color: #ffffff; }
    </style>
</head>
<body>
<div class="container py-5" style="max-width: 860px;">
    <div class="text-center mb-4">
        <h2 class="fw-bold text-white">Observer Settings Generator</h2>
        <p class="text-secondary">Configure your parameters to automatically generate <code>variables.py</code></p>
    </div>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }} alert-dismissible fade show mb-4" role="alert">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
          </div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="POST" action="/save">
        
        <!-- REQUIRED VARIABLES CARD -->
        <div class="card shadow">
            <div class="card-header card-header-required d-flex justify-content-between align-items-center py-3">
                <span>Required Variables</span>
                <span class="badge badge-req">REQUIRED</span>
            </div>
            <div class="card-body p-4">
                <div class="mb-3">
                    <label for="topic" class="form-label">Topic</label>
                    <input type="text" class="form-control" id="topic" name="topic" value="{{ config.topic }}" required>
                    <div class="help-text">Your unique notification topic string.</div>
                </div>

                <div class="row g-3 mb-3">
                    <div class="col-md-4">
                        <label for="latitude" class="form-label">Latitude</label>
                        <input type="text" class="form-control" id="latitude" name="latitude" value="{{ config.latitude }}" required>
                        <div class="help-text">e.g. 52.5200</div>
                    </div>
                    <div class="col-md-4">
                        <label for="longitude" class="form-label">Longitude</label>
                        <input type="text" class="form-control" id="longitude" name="longitude" value="{{ config.longitude }}" required>
                        <div class="help-text">e.g. 13.4050</div>
                    </div>
                    <div class="col-md-4">
                        <label for="elevation" class="form-label">Elevation (m)</label>
                        <input type="text" class="form-control" id="elevation" name="elevation" value="{{ config.elevation }}" required>
                        <div class="help-text">Altitude in meters above sea level</div>
                    </div>
                </div>

                <div class="mb-2">
                    <label for="local_timezone" class="form-label">Local Timezone</label>
                    <select class="form-select" id="local_timezone" name="local_timezone" required>
                        {% for tz in timezones %}
                            <option value="{{ tz }}" {% if tz == config.local_timezone %}selected{% endif %}>{{ tz }}</option>
                        {% endfor %}
                    </select>
                    <div class="help-text">IANA Time Zone database string.</div>
                </div>
            </div>
        </div>

        <!-- OPTIONAL VARIABLES CARD -->
        <div class="card shadow">
            <div class="card-header card-header-optional d-flex justify-content-between align-items-center py-3">
                <span>Optional Variables</span>
                <span class="badge badge-opt">OPTIONAL</span>
            </div>
            <div class="card-body p-4">
                <div class="row g-3 mb-4">
                    <div class="col-md-4">
                        <label for="kp_treshold" class="form-label">Kp Threshold</label>
                        <input type="number" class="form-control" id="kp_treshold" name="kp_treshold" value="{{ config.kp_treshold }}">
                        <div class="help-text">Notify if Kp index exceeds this</div>
                    </div>
                    <div class="col-md-4">
                        <label for="total_sunspot_area_treshold" class="form-label">Sunspot Area Threshold</label>
                        <input type="number" class="form-control" id="total_sunspot_area_treshold" name="total_sunspot_area_treshold" value="{{ config.total_sunspot_area_treshold }}">
                        <div class="help-text">Measured in MH</div>
                    </div>
                    <div class="col-md-4">
                        <label for="comet_mag_treshold" class="form-label">Comet Mag Threshold</label>
                        <input type="number" step="0.1" class="form-control" id="comet_mag_treshold" name="comet_mag_treshold" value="{{ config.comet_mag_treshold }}">
                        <div class="help-text">Notify if brighter than magnitude</div>
                    </div>
                </div>

                <div class="row g-3 mb-4">
                    <div class="col-md-6">
                        <label for="horizon_north_offset" class="form-label">Horizon North Offset (°)</label>
                        <input type="number" class="form-control" id="horizon_north_offset" name="horizon_north_offset" value="{{ config.horizon_north_offset }}" min="-360" max="360">
                        <div class="help-text">Degrees offset from true north (-360 to +360)</div>
                    </div>
                    <div class="col-md-6">
                        <label for="days_in_advance" class="form-label">Days in Advance</label>
                        <input type="number" class="form-control" id="days_in_advance" name="days_in_advance" value="{{ config.days_in_advance }}">
                        <div class="help-text">Days ahead for eclipse notifications</div>
                    </div>
                </div>

                <div class="row g-3 mb-4">
                    <div class="col-md-6">
                        <div class="form-check form-switch mt-2">
                            <input class="form-check-input" type="checkbox" id="include_observation_horizon" name="include_observation_horizon" {% if config.include_observation_horizon %}checked{% endif %}>
                            <label class="form-check-label ms-2" for="include_observation_horizon">Include Observation Horizon</label>
                        </div>
                        <div class="help-text ms-4">Set True if using custom <code>horizon.png</code></div>
                    </div>
                    <div class="col-md-6">
                        <div class="form-check form-switch mt-2">
                            <input class="form-check-input" type="checkbox" id="redirect_to_website" name="redirect_to_website" {% if config.redirect_to_website %}checked{% endif %}>
                            <label class="form-check-label ms-2" for="redirect_to_website">Redirect to Website</label>
                        </div>
                        <div class="help-text ms-4">Redirect to website when clicking notification</div>
                    </div>
                </div>

                <hr class="border-secondary my-4">
                <h6 class="fw-bold mb-3 text-light">Notification Info (Active Months & Enable Toggles)</h6>
                
                {% set event_labels = {
                    'northern_lights': 'Northern Lights',
                    'transit': 'Transit',
                    'sunspot': 'Sunspot',
                    'comet': 'Comet',
                    'eclipse': 'Eclipse'
                } %}

                {% for key, label in event_labels.items() %}
                <div class="row align-items-center mb-3">
                    <div class="col-md-3">
                        <span class="fw-medium text-slate-200">{{ label }}</span>
                    </div>
                    <div class="col-md-3">
                        <select class="form-select form-select-sm" name="{{ key }}_from">
                            {% for m in months %}
                                <option value="{{ m }}" {% if config.notification_info[key][0][0] == m %}selected{% endif %}>{{ m }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-md-3">
                        <select class="form-select form-select-sm" name="{{ key }}_to">
                            {% for m in months %}
                                <option value="{{ m }}" {% if config.notification_info[key][0][1] == m %}selected{% endif %}>{{ m }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-md-3">
                        <div class="form-check form-switch ms-2">
                            <input class="form-check-input" type="checkbox" id="{{ key }}_enabled" name="{{ key }}_enabled" {% if config.notification_info[key][1] %}checked{% endif %}>
                            <label class="form-check-label small" for="{{ key }}_enabled">Notify</label>
                        </div>
                    </div>
                </div>
                {% endfor %}

            </div>
        </div>

        <div class="text-center mt-4">
            <button type="submit" class="btn btn-save shadow">Save to variables.py</button>
        </div>
    </form>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    timezones = sorted(zoneinfo.available_timezones())
    return render_template_string(HTML_TEMPLATE, config=DEFAULT_CONFIG, timezones=timezones, months=MONTHS)

@app.route("/save", methods=["POST"])
def save():
    topic = request.form.get("topic", "")
    latitude = request.form.get("latitude", "52.5200")
    longitude = request.form.get("longitude", "13.4050")
    elevation = request.form.get("elevation", "38")
    local_timezone = request.form.get("local_timezone", "Europe/Berlin")

    kp_treshold = request.form.get("kp_treshold", "6")
    total_sunspot_area_treshold = request.form.get("total_sunspot_area_treshold", "1500")
    comet_mag_treshold = request.form.get("comet_mag_treshold", "7")

    include_observation_horizon = "include_observation_horizon" in request.form
    horizon_north_offset = request.form.get("horizon_north_offset", "0")

    redirect_to_website = "redirect_to_website" in request.form
    days_in_advance = request.form.get("days_in_advance", "30")

    events = ["northern_lights", "transit", "sunspot", "comet", "eclipse"]
    notif_entries = []
    for ev in events:
        m_from = request.form.get(f"{ev}_from", "Jan")
        m_to = request.form.get(f"{ev}_to", "Dec")
        enabled = f"{ev}_enabled" in request.form
        # Match formatting padding
        padding = " " * (18 - len(ev))
        notif_entries.append(f'    "{ev}":{padding}(("{m_from}", "{m_to}"), {enabled})')

    notif_str = "{\n" + ",\n".join(notif_entries) + "\n}"

    file_content = f'''topic = "{topic}"                      # Your topic
latitude = "{latitude}"                # Your latitude
longitude = "{longitude}"               # Your longitude
elevation = "{elevation}"                    # Your altitude in meters above sea level
local_timezone = "{local_timezone}"    # The timezone of where you will be observing from (IANA Time Zone Database)

# Optional changes:
kp_treshold = {kp_treshold}                     # If kp exceeds this value, you will be notified
total_sunspot_area_treshold = {total_sunspot_area_treshold}  # If the total area (measured in MH) of all sunspots exceeds this value, you will be notified
comet_mag_treshold = {comet_mag_treshold}              # Any comet with a magnitude lower than this number will notify you

include_observation_horizon = {include_observation_horizon} # Leave this False if you will not be adding your own horizon.png image, else change to True
horizon_north_offset = {horizon_north_offset}            # How many degrees offset is your image from true north (-360 to +360)

redirect_to_website = {redirect_to_website}         # Decides if you should be redirected to a relevant website when clicking a notification (True/False)

days_in_advance = {days_in_advance}                # How many days in advance of solar/lunar eclipses you will recieve notifications

# ((from month, to month), should this event notify you? (True/False))
# E.g. ("Jan", "Dec") will notify you the whole year, ("Apr", "Sep") will notify you from april to september
notification_info = {notif_str}

""" Prints all available timezones
import zoneinfo
timezones = sorted(zoneinfo.available_timezones())
for t in timezones:
    print(t)
"""

from zoneinfo import ZoneInfo
localtime = ZoneInfo(local_timezone)
'''

    with open("variables.py", "w", encoding="utf-8") as f:
        f.write(file_content)

    flash("Saved configuration to variables.py!", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)