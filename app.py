from variables import latitude, longitude, localtime
import tempfile
import math
import requests
from datetime import datetime
from suncalc import get_position
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

def get_lowest_sun_altitude(dt: datetime, lat: float, lon: float) -> float:
    """Calculates lowest sun altitude for any day at any location"""
    local_dt = datetime(dt.year, dt.month, dt.day, tzinfo=localtime)
    times = []
    for h in range(24):
        for m in range(2):
            times.append(local_dt.replace(hour=h, minute=m*30))

    sun_alts = []
    for check_time in times:
        position = get_position(check_time, lon, lat)
        sun_alts.append(math.degrees(position["altitude"]))

    return min(sun_alts)

def get_edge_months(months) -> list:
    """
    Find the edge months in a list of months.
    Returns [last_month_before_gap, first_month_after_gap]
    If no gap exists, returns [first_month, last_month]
    """
    if not months:
        return []
    
    months = sorted(months)
    
    # Find gaps in the sequence
    for i in range(len(months) - 1):
        if months[i + 1] - months[i] > 1:
            # Found a gap
            return [months[i], months[i + 1]]
    
    # No gap found, return first and last
    return [months[0], months[-1]]

def get_dark_months() -> list:
    astronomical_darkness_months = []
    for m in range(1, 13):
        for d in range(1, 6):
            lowest_alt = get_lowest_sun_altitude(
                datetime.now(tz=localtime).replace(month=m, day=d*5),
                float(latitude),
                float(longitude)
            )
            if lowest_alt <= -18:
                if m not in astronomical_darkness_months:
                    astronomical_darkness_months.append(m)

    return get_edge_months(astronomical_darkness_months)

BASE_DIR = Path(__file__).resolve().parent
EXAMPLE_FILE = BASE_DIR / "variables_example.py"
TARGET_FILE = BASE_DIR / "variables_test.py"
SKY_SURVEY_FILE = BASE_DIR / "sky-survey-test.jpg"
UPLOAD_FOLDER = BASE_DIR / "obs_horizon"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# NOIRLab noirlab2430b — "All-sky photo of the night sky" (40000x20000px source)
# Format keys confirmed against https://noirlab.edu/public/image-formats/
SKY_SURVEY_URLS = {
    "large": "https://noirlab.edu/public/media/archives/images/large/noirlab2430b.jpg",
    "publication": "https://noirlab.edu/public/media/archives/images/publicationjpg/noirlab2430b.jpg",
}

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/calculate_months')
def calculate_months():
    mapping_table = {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Aug",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dec"
    }
    # Read latitude and longitude from variables.py
    dark_months = get_dark_months()

    return jsonify({"months": [mapping_table[dark_months[1]], mapping_table[dark_months[0]]]})

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if file was uploaded
    if 'file' not in request.files:
        return jsonify(ok=False, error="No file part in the request."), 400

    file = request.files['file']

    # If user submitted empty form
    if file.filename == '':
        return jsonify(ok=False, error="No selected file."), 400

    # Secure the filename and save into obs_horizon
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify(ok=False, error="Invalid filename."), 400

    try:
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        file.save(UPLOAD_FOLDER / filename)
    except OSError as exc:
        return jsonify(ok=False, error=str(exc)), 500

    return jsonify(ok=True, filename=filename, path=str(UPLOAD_FOLDER / filename))

@app.route("/api/save", methods=["POST"])
def save_variables():
    data = request.get_json(silent=True) or {}
    content = data.get("content")

    if not content or not isinstance(content, str):
        return jsonify(ok=False, error="No content received."), 400

    try:
        if not TARGET_FILE.exists():
            TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
        TARGET_FILE.write_text(content, encoding="utf-8")
    except OSError as exc:
        return jsonify(ok=False, error=str(exc)), 500

    return jsonify(ok=True, path=str(TARGET_FILE))

@app.route("/api/download-sky-survey", methods=["POST"])
def download_sky_survey():
    data = request.get_json(silent=True) or {}
    quality = data.get("quality")

    url = SKY_SURVEY_URLS.get(quality)
    if not url:
        return jsonify(ok=False, error="quality must be 'large' or 'publication'."), 400

    tmp_path = None
    try:
        with requests.get(url, stream=True, timeout=(10, 60)) as resp:
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(
                dir=BASE_DIR, suffix=".part", delete=False
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        tmp_file.write(chunk)

        # Only replace the real file once the download has fully succeeded.
        tmp_path.replace(SKY_SURVEY_FILE)
        size_bytes = SKY_SURVEY_FILE.stat().st_size
    except (requests.RequestException, OSError) as exc:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return jsonify(ok=False, error=str(exc)), 500

    return jsonify(ok=True, path=str(SKY_SURVEY_FILE), size_bytes=size_bytes)


if __name__ == "__main__":
    # threaded=True so the sky-survey download (which can take a while) doesn't block the rest of the app.
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)