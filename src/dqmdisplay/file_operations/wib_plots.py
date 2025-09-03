import re
from dqmdisplay.file_operations.gather_files import filter_files


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