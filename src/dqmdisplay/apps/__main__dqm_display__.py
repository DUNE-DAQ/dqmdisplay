from pathlib import Path

from flask import Flask, send_from_directory, render_template 

from dqmdisplay.file_operations.dqm_display import DQMDisplay

app = Flask(__name__)

# Set the directory you want to serve the images from
IMAGE_DIRECTORY = '/nfs/rscratch/np04daq'

# Store the last modification time
last_mod_time = 0

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
    global IMAGE_DIRECTORY

    IMAGE_DIRECTORY = image_dir
    db = DQMDisplay(IMAGE_DIRECTORY)
    db.link_app(app)
    
    
    app.run(debug=True, host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()