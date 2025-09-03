import re
from dqmdisplay.file_operations.gather_files import filter_files


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
