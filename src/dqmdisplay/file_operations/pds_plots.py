import re
from dqmdisplay.file_operations.gather_files import filter_files


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
