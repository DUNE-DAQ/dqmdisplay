import pandas as pd
import os
import re

def gather_files(directory, filename_regex, to_find=['run', 'trigger', 'element_id', 'plane']):
    '''
    Gather all files in a directory matching some regex
    '''
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


def build_run_trigger_lookup(image_directory):
    """
    Build a lookup dict of all available objects per run/trigger.
    Scans each directory only once for speed.
    Returns a dict sorted by run and trigger.
    """
    lookup = {}

    # --- EventDisplays ---
    evd_dir = os.path.join(image_directory, "EventDisplays")
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
    wib_dir = os.path.join(image_directory, "WIBTests")
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
    pds_dir = os.path.join(image_directory, "pds_plots")
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
