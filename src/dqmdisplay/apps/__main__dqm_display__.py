from pathlib import Path

from flask import Flask, send_from_directory, render_template 

from dqmdisplay.file_operations.dqm_display import DQMDisplayApp

app = Flask(__name__)

# Set the directory you want to serve the images from
IMAGE_DIRECTORY = '/nfs/rscratch/np04daq'

# Store the DQMDisplayApp instance
_db_instance = None

def get_db():
    """Get or create the DQMDisplayApp instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DQMDisplayApp(IMAGE_DIRECTORY)
        _db_instance.link_app(app)
    return _db_instance

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


import click
@click.command()
@click.argument('image_dir', type=click.Path(exists=True))
@click.option('--port', default=8005, help='Which port to run the image browser on')
def main(image_dir, port):
    global IMAGE_DIRECTORY, _db_instance

    IMAGE_DIRECTORY = image_dir
    # Reset the instance to force re-initialization with new directory
    _db_instance = None
    
    # Initialize the database before running the app
    db = get_db()
    
    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=True)

if __name__ == '__main__':
    main()