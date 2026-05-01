from pathlib import Path

import click
from flask import Flask, send_from_directory, render_template

from dqmdisplay.file_operations.dqm_display import DQMDisplayApp

app = Flask(__name__)

IMAGE_DIRECTORY = '/nfs/rscratch/np04daq'
_dqm_app: DQMDisplayApp | None = None

# How often (seconds) the server re-scans the image directory for new files.
REFRESH_INTERVAL_S = 30


@app.before_request
def refresh_file_database():
    if _dqm_app is not None:
        _dqm_app.database_collection.refresh_all(min_interval_s=REFRESH_INTERVAL_S)


@app.route('/')
@app.route('/index')
@app.route('/home')
def index():
    return render_template('index.html')


@app.route('/images/<subdir>/<path:filename>')
def serve_image(subdir, filename):
    path = Path(IMAGE_DIRECTORY) / subdir / filename
    if not path.exists():
        raise RuntimeError(f"Couldn't make path to {path}")
    return send_from_directory(IMAGE_DIRECTORY + "/" + subdir, filename)


@click.command()
@click.argument('image_dir', type=click.Path(exists=True))
@click.option('--port', default=8005, help='Which port to run the image browser on')
@click.option('--refresh-interval', default=REFRESH_INTERVAL_S, show_default=True,
              help='Seconds between directory re-scans for new images')
def main(image_dir, port, refresh_interval):
    global IMAGE_DIRECTORY, _dqm_app, REFRESH_INTERVAL_S

    IMAGE_DIRECTORY = image_dir
    REFRESH_INTERVAL_S = refresh_interval

    _dqm_app = DQMDisplayApp(IMAGE_DIRECTORY)
    _dqm_app.link_app(app)

    app.run(debug=True, host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()