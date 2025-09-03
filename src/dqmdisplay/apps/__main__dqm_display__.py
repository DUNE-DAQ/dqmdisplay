from flask import Flask, send_from_directory, render_template 
from dqmdisplay.file_operations.pds_plots import get_pds_plots, get_latest_pds_plots
from dqmdisplay.file_operations.wib_plots import get_WIBTests_files, get_latest_WIBTests_files
from dqmdisplay.file_operations.event_display_plots import get_EventDisplay_files, get_latest_EventDisplay_files, build_run_trigger_lookup

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

@app.route('/plot_navigator')
def plot_navigator():
    run_trigger_data = build_run_trigger_lookup(IMAGE_DIRECTORY)
    return render_template('plot_navigator.html', run_trigger_data=run_trigger_data)

# Latest objects
@app.route('/event_display/latest')
@app.route('/event_display/latest/apa<ele>')
@app.route('/event_display/latest/apa<ele>_plane<plane>')
@app.route('/event_display/latest/crp<ele>')
@app.route('/event_display/latest/crp<ele>_plane<plane>')
def latest_event_display(ele=None, plane=None):
    evd_images = get_latest_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays", select_element=ele, select_plane=plane)
    return render_template('event_display.html', images=evd_images, ele=ele, plane=plane)

@app.route('/event_display_grid/latest/apa<ele>')
@app.route('/event_display_grid/latest/crp<ele>')
def latest_event_display_grid(ele=None):
    evd_images = get_latest_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays", select_element=ele)
    return render_template('event_display_grid.html', images=evd_images, ele=ele)

@app.route('/event_display_plane/latest/plane<plane>')
def latest_event_display_plane(plane=None):
    if plane is None: 
        plane = 2
    evd_images = get_latest_EventDisplay_files(IMAGE_DIRECTORY+"/EventDisplays", select_plane=plane)
    return render_template('event_display_plane.html', images=evd_images, plane=plane)

@app.route('/tests/latest/wibs')
def latest_tests_wibs():
    test_images = get_latest_WIBTests_files(IMAGE_DIRECTORY+"/WIBTests")
    return render_template('tests_wibs.html', images=test_images)

@app.route('/latest/pds')
def latest_pds():
    images = get_latest_pds_plots(IMAGE_DIRECTORY+"/pds_plots")
    return render_template("pds.html", images=images)


# Run/trigger specific objects
@app.route('/event_display/run<run>/')
@app.route('/event_display/run<run>/trigger<trigger>')
@app.route('/event_display/run<run>/trigger<trigger>/apa<ele>')
@app.route('/event_display/run<run>/trigger<trigger>/apa<ele>_plane<plane>')
@app.route('/event_display/run<run>/trigger<trigger>/crp<ele>')
@app.route('/event_display/run<run>/trigger<trigger>/crp<ele>_plane<plane>')
def run_trigger_event_display(run=None, trigger=None, ele=None, plane=None):
    evd_images = get_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays", select_run=run, select_trigger=trigger,
                                        select_element=ele, select_plane=plane)
    return render_template('event_display.html', images=evd_images, run=run, trigger=trigger, ele=ele, plane=plane)

@app.route('/event_display_grid/run<run>/trigger<trigger>/apa<ele>')
@app.route('/event_display_grid/run<run>/trigger<trigger>/crp<ele>')
def run_trigger_event_display_grid(run=None, trigger=None, ele=None):
    evd_images = get_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays", select_run=run, select_trigger=trigger,
                                        select_element=ele)
    return render_template('event_display_grid.html', images=evd_images, run=run, trigger=trigger, ele=ele)

@app.route('/event_display_plane/run<run>/trigger<trigger>/plane<plane>')
def run_trigger_event_display_plane(run=None, trigger=None, plane=None):
    if plane is None: 
        plane = 2
    evd_images = get_EventDisplay_files(IMAGE_DIRECTORY+"/EventDisplays", select_run=run,  # Fixed: was "EventDisplay"
                                        select_trigger=trigger, select_plane=plane)
    return render_template('event_display_plane.html', images=evd_images, run=run, trigger=trigger, plane=plane)

@app.route('/tests/run<run>/trigger<trigger>/wibs')
def run_trigger_tests_wibs(run=None, trigger=None):
    test_images = get_WIBTests_files(IMAGE_DIRECTORY+"/WIBTests", select_run=run, select_trigger=trigger)
    return render_template('tests_wibs.html', images=test_images, run=run, trigger=trigger)

@app.route('/run<run>/trigger<trigger>/pds')
def run_trigger_pds(run=None, trigger=None):
    images = get_pds_plots(IMAGE_DIRECTORY+"/pds_plots", select_run=run, select_trigger=trigger)
    return render_template("pds.html", images=images, run=run, trigger=trigger)

@app.route('/images/<subdir>/<path:filename>')
def serve_image(subdir, filename):
    return send_from_directory(IMAGE_DIRECTORY + "/" + subdir, filename)


import click
@click.command()
@click.argument('image_dir', type=click.Path(exists=True))
@click.option('--port', default=8005, help='Which port to run the image browser on')
def main(image_dir, port):
    global IMAGE_DIRECTORY

    IMAGE_DIRECTORY = image_dir
    
    app.run(debug=True, host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()