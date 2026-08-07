from datetime import datetime
from suncalc import get_position
from variables import latitude, longitude

"""current_date = datetime.now()
sun_pos = get_position(current_date, float(longitude), float(latitude))

altitude_rad = sun_pos['altitude']
altitude_deg = altitude_rad * (180.0 / 3.141592653589793)

print(f"Sun Altitude: {altitude_deg:.2f}°")"""

import tempfile
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
EXAMPLE_FILE = BASE_DIR / "variables_example.py"
TARGET_FILE = BASE_DIR / "variables_test.py"
SKY_SURVEY_FILE = BASE_DIR / "sky-survey.jpg"
UPLOAD_FOLDER = BASE_DIR / "obs_horizon"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# NOIRLab noirlab2430b — "All-sky photo of the night sky" (40000x20000px
# source). Format keys confirmed against https://noirlab.edu/public/image-formats/
SKY_SURVEY_URLS = {
    "large": "https://noirlab.edu/public/media/archives/images/large/noirlab2430b.jpg",
    "publication": "https://noirlab.edu/public/media/archives/images/publicationjpg/noirlab2430b.jpg",
}

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

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
        """if EXAMPLE_FILE.exists():
            # Write the new config into variables_example.py, then rename
            # that file to variables.py (replacing any existing one).
            EXAMPLE_FILE.write_text(content, encoding="utf-8")
            if TARGET_FILE.exists() and TARGET_FILE != EXAMPLE_FILE:
                TARGET_FILE.unlink()
            EXAMPLE_FILE.rename(TARGET_FILE)"""
        #else:
            # No example file to rename — just write variables.py directly.
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
    # Port 5050 to avoid clashing with macOS AirPlay on 5000.
    # threaded=True so the sky-survey download (which can take a while)
    # doesn't block the rest of the app.
    app.run(host="127.0.0.1", port=5050, debug=True, threaded=True)