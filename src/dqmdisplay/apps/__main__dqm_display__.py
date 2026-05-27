import logging
import time
import threading
import traceback
from pathlib import Path

import click
from flask import Flask, send_from_directory, render_template, make_response

from dqmdisplay.file_operations.dqm_display import DQMDisplayApp

app = Flask(__name__)

IMAGE_DIRECTORY = '/nfs/rscratch/np04daq'
_dqm_app: DQMDisplayApp | None = None
REFRESH_INTERVAL_S = 30


_log = logging.getLogger('dqmdisplay.scanner')


def _scan_loop():
    '''Background daemon: checks for new image files every REFRESH_INTERVAL_S seconds.
    Runs completely independently of HTTP request handling — zero request latency impact.
    Exceptions are logged and swallowed so the thread never dies silently.'''
    while True:
        time.sleep(REFRESH_INTERVAL_S)
        if _dqm_app is None:
            continue
        try:
            _dqm_app.database_collection.refresh_all()
        except Exception:
            _log.error('Unhandled exception in file-scanner thread — scan skipped:\n%s',
                       traceback.format_exc())


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
    resp = make_response(send_from_directory(IMAGE_DIRECTORY + '/' + subdir, filename))
    # Images have unique names per run/trigger so caching is safe; avoids re-fetching
    # unchanged images on every 30-second page reload.
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


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

    # Background scanner — daemon so it exits with the main process
    scanner = threading.Thread(target=_scan_loop, daemon=True, name='file-scanner')
    scanner.start()

    # threaded=True: serve images concurrently while the HTML page loads
    # use_reloader=False: prevents werkzeug from spawning a second process that
    #   would also start a second background scanner thread
    app.run(debug=True, host='0.0.0.0', port=port,
            threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()
