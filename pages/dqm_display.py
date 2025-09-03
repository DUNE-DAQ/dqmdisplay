from flask import Flask, send_from_directory, render_template 
import re
import os
import pandas as pd

app = Flask(__name__)

# Set the directory you want to serve the images from
IMAGE_DIRECTORY = '/nfs/rscratch/np04daq'

# Store the last modification time
last_mod_time = 0

def gather_files(directory, filename_regex, to_find=['run', 'trigger', 'element_id', 'plane']):
    file_dict = {k : [] for k in to_find}
    file_dict['filename'] = []
    
    for filename in os.listdir(directory):
        match = filename_regex.match(filename)
        if not match:
            continue

        for name in to_find:
            file_dict[name].append(int(match[name]))
        file_dict['filename'].append(filename)

    return_df = pd.DataFrame.from_dict(file_dict)
    return return_df

def filter_files(directory, filename_regex, to_find=['run', 'trigger', 'element_id', 'plane'], filters: dict={}):
    '''
    Filter out unwanted entries
    '''
    
    event_file_df = gather_files(directory, filename_regex, to_find)
    
    for filter, val in filters.items():
        if val is None:
            continue
        event_file_df = event_file_df[event_file_df[filter]==int(val)]
    return event_file_df


def get_pds_plots(directory, select_run=None, select_trigger=None):
    filename_regex = re.compile(r"run(?P<run>\d+)_(?P<trigger>\d+)_([^_]+)\.svg")
    filtered_df = filter_files(directory, filename_regex, to_find=['run', 'trigger'], 
                              filters={'run': select_run, 'trigger': select_trigger})
    return filtered_df['filename'].to_list()
    
def get_latest_pds_plots(directory):
    filename_regex = re.compile(r"run(?P<run>\d+)_(?P<trigger>\d+)_([^_]+)\.svg")
    filename_df = filter_files(directory, filename_regex, to_find=['run', 'trigger'])
    if filename_df.empty:
        return []
    max_image = filename_df.sort_values(['run','trigger'], ascending=[False, False]).iloc[0]['filename']
    return [max_image]


def get_WIBTests_files(directory, select_run=None, select_trigger=None):
    filename_regex = re.compile(r"Tests_WIBS_results_run(?P<run>\d+)_trigger(?P<trigger>\d+)\.[^.]+")    
    filename_df = filter_files(directory, filename_regex, ['run', 'trigger'], 
                              filters={'run': select_run, 'trigger': select_trigger})
    return filename_df['filename'].to_list()
    
def get_latest_WIBTests_files(directory):
    filename_regex = re.compile(r"Tests_WIBS_results_run(?P<run>\d+)_trigger(?P<trigger>\d+)\.[^.]+")    
    filename_df = filter_files(directory, filename_regex, ['run', 'trigger'])
    if filename_df.empty:
        return []
    max_image = filename_df.sort_values(['run','trigger'], ascending=[False, False]).iloc[0]['filename']
    return [max_image]

def get_EventDisplay_files(directory, select_run=None, select_trigger=None, select_element=None, select_plane=None):
    filename_regex = re.compile(
        r"""^EventDisplay_run(?P<run>\d+)
            _trigger(?P<trigger>\d+)
            _seq\d+
            _(?P<element_type>APA|CRP)(?P<element_id>\d+)?     # APA<digits> or CRP[digits optional]
            _plane(?P<plane>\d+)\.png$""",
        re.X
    )
    filtered_df = filter_files(directory, filename_regex, 
                              filters={'run': select_run,
                                     'trigger': select_trigger, 
                                     'element_id': select_element,
                                     'plane': select_plane})  # Fixed: was 'plane_id'
    
    return filtered_df['filename'].to_list()


def get_latest_EventDisplay_files(directory, select_element=None, select_plane=None):
    filename_regex = re.compile(
        r"""^EventDisplay_run(?P<run>\d+)
            _trigger(?P<trigger>\d+)
            _seq\d+
            _(?P<element_type>APA|CRP)(?P<element_id>\d+)?     # APA<digits> or CRP[digits optional]
            _plane(?P<plane>\d+)\.png$""",
        re.X
    )
    
    filtered_df = filter_files(directory, filename_regex, 
                              filters={'element_id': select_element, 'plane': select_plane})
    
    if filtered_df.empty:
        return []
    
    max_for_el_plane = (filtered_df.sort_values(['run', 'trigger'], ascending=[False, False])
          .drop_duplicates(['element_id', 'plane'], keep='first')).sort_values(['element_id','plane'])

    return max_for_el_plane['filename'].to_list()


def get_all_run_trigger_combinations():
    """
    Get all available run/trigger combinations from all data sources
    """
    run_trigger_sets = []
    
    # Get from EventDisplays
    try:
        filename_regex = re.compile(
            r"""^EventDisplay_run(?P<run>\d+)
                _trigger(?P<trigger>\d+)
                _seq\d+
                _(?P<element_type>APA|CRP)(?P<element_id>\d+)?     # APA<digits> or CRP[digits optional]
                _plane(?P<plane>\d+)\.png$""",
            re.X
        )
        event_display_df = filter_files(IMAGE_DIRECTORY + "/EventDisplays", filename_regex)
        if not event_display_df.empty:
            run_trigger_sets.append(event_display_df[['run', 'trigger']].drop_duplicates())
    except Exception as e:
        print(f"Error reading EventDisplays: {e}")
        pass
    
    # Get from WIBTests
    try:
        filename_regex = re.compile(r"Tests_WIBS_results_run(?P<run>\d+)_trigger(?P<trigger>\d+)\.[^.]+")
        wib_tests_df = filter_files(IMAGE_DIRECTORY + "/WIBTests", filename_regex, ['run', 'trigger'])
        if not wib_tests_df.empty:
            run_trigger_sets.append(wib_tests_df[['run', 'trigger']].drop_duplicates())
    except Exception as e:
        print(f"Error reading WIBTests: {e}")
        pass
    
    # Get from PDS plots
    try:
        filename_regex = re.compile(r"run(?P<run>\d+)_(?P<trigger>\d+)_([^_]+)\.svg")
        pds_df = filter_files(IMAGE_DIRECTORY + "/pds_plots", filename_regex, to_find=['run', 'trigger'])
        if not pds_df.empty:
            run_trigger_sets.append(pds_df[['run', 'trigger']].drop_duplicates())
    except Exception as e:
        print(f"Error reading PDS plots: {e}")
        pass
    
    # Combine all run/trigger combinations
    if run_trigger_sets:
        all_combinations = pd.concat(run_trigger_sets).drop_duplicates().sort_values(['run', 'trigger'])
        
        # Group by run and create the hierarchical structure
        run_trigger_dict = {}
        for _, row in all_combinations.iterrows():
            run = int(row['run'])
            trigger = int(row['trigger'])
            if run not in run_trigger_dict:
                run_trigger_dict[run] = []
            run_trigger_dict[run].append(trigger)
        
        # Sort triggers within each run
        for run in run_trigger_dict:
            run_trigger_dict[run].sort()
        
        return run_trigger_dict
    
    return {}

def get_run_trigger_data_with_availability():
    '''We don't need to render everything!'''
    runs_triggers = get_all_run_trigger_combinations()
    result = {}

    for run, triggers in runs_triggers.items():
        result[run] = {}
        for trigger in triggers:
            result[run][trigger] = {
                "event_display": {ele: bool(get_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays",
                                                                   select_run=run,
                                                                   select_trigger=trigger,
                                                                   select_element=ele)) 
                                  for ele in [1,2,3,4,5]},
                "plane_display": {plane: bool(get_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays",
                                                                     select_run=run,
                                                                     select_trigger=trigger,
                                                                     select_plane=plane)) 
                                  for plane in [0,1,2]},
                "wib_tests": bool(get_WIBTests_files(IMAGE_DIRECTORY + "/WIBTests",
                                                     select_run=run, select_trigger=trigger)),
                "pds": bool(get_pds_plots(IMAGE_DIRECTORY + "/pds_plots",
                                          select_run=run, select_trigger=trigger))
            }
    return result


def build_run_trigger_lookup():
    """
    Build a lookup dict of all available objects per run/trigger.
    Scans each directory only once for speed.
    Returns a dict sorted by run and trigger.
    """
    lookup = {}

    # --- EventDisplays ---
    evd_dir = os.path.join(IMAGE_DIRECTORY, "EventDisplays")
    evd_regex = re.compile(
        r"^EventDisplay_run(?P<run>\d+)_trigger(?P<trigger>\d+)_seq\d+_(?P<type>APA|CRP)(?P<ele>\d+)?_plane(?P<plane>\d+)\.png$"
    )

    if os.path.exists(evd_dir):
        for fname in os.listdir(evd_dir):
            match = evd_regex.match(fname)
            if not match:
                continue
            run = int(match.group('run'))
            trigger = int(match.group('trigger'))
            ele = int(match.group('ele')) if match.group('ele') else None
            plane = int(match.group('plane'))

            lookup.setdefault(run, {}).setdefault(trigger, {
                "event_display": {},
                "plane_display": {},
                "wib_tests": False,
                "pds": False
            })

            if ele is not None:
                lookup[run][trigger]["event_display"][ele] = True
            lookup[run][trigger]["plane_display"][plane] = True

    # --- WIB Tests ---
    wib_dir = os.path.join(IMAGE_DIRECTORY, "WIBTests")
    wib_regex = re.compile(r"Tests_WIBS_results_run(?P<run>\d+)_trigger(?P<trigger>\d+)\.[^.]+")
    if os.path.exists(wib_dir):
        for fname in os.listdir(wib_dir):
            match = wib_regex.match(fname)
            if not match:
                continue
            run = int(match.group('run'))
            trigger = int(match.group('trigger'))
            lookup.setdefault(run, {}).setdefault(trigger, {
                "event_display": {},
                "plane_display": {},
                "wib_tests": False,
                "pds": False
            })["wib_tests"] = True

    # --- PDS Plots ---
    pds_dir = os.path.join(IMAGE_DIRECTORY, "pds_plots")
    pds_regex = re.compile(r"run(?P<run>\d+)_(?P<trigger>\d+)_.*\.svg")
    if os.path.exists(pds_dir):
        for fname in os.listdir(pds_dir):
            match = pds_regex.match(fname)
            if not match:
                continue
            run = int(match.group('run'))
            trigger = int(match.group('trigger'))
            lookup.setdefault(run, {}).setdefault(trigger, {
                "event_display": {},
                "plane_display": {},
                "wib_tests": False,
                "pds": False
            })["pds"] = True

    # --- Sort the dict by run and trigger ---
    sorted_lookup = {run: {trigger: lookup[run][trigger]
                           for trigger in sorted(lookup[run], reverse=True)}
                     for run in sorted(lookup, reverse=True)}

    return sorted_lookup

@app.route('/')
@app.route('/index')
@app.route('/home')
def index():
    return render_template('index.html')

@app.route('/plot_navigator')
def plot_navigator():
    run_trigger_data = build_run_trigger_lookup()
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