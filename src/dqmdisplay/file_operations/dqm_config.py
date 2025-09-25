from dataclasses import dataclass, field
from typing import List, Optional, Any
from pathlib import Path


@dataclass
class ViewData:
    html: str
    # Use American spelling cos HTML...
    title: str
    cols_to_search: List[str] = field(default_factory=lambda: [])
    name: str = "default"

    def view_name_full(self, sub: Any):
        return self.title.replace("{sub_option}", sub)

@dataclass
class DisplayData:
    # Display data
    name: str
    subdirectory: Path | str
    regex: str
    views: list
    title: str
    all_columns_to_show: List[str] = field(default_factory=lambda: ['run', 'trigger'])
 
 
'''
HW: PLACEHOLDER! Can now be made more configurable easily but I'm ... lazy
'''
class DisplayConfig():
    CONFIG_DICT = {
        'event_display': {
            # Directory to find things in 
            'directory' : "EventDisplays",
            # Regex to search
            'regex' : r"""^EventDisplay_run(?P<run>\d+)
                         _trigger(?P<trigger>\d+)
                        _seq\d+
                        _(?P<element_type>APA|CRP)(?P<element_id>\d+)? 
                        _plane(?P<plane>\d+)\.png$""",
            # Additional columns to add
            'all_columns_to_show': ['element_id', 'plane'],
            'title': 'Event Displays',
            
            # Other views {view_name: options to add} (does nothing rn, this is hardcoded later...)
            'views':  {
                            'event_display': {
                                'cols_to_search': ['element_id'],
                                'html': 'event_display.html',
                                'title': 'APA/CRP {sub_option} Display'
                                
                            },
                            'grid': {
                                'cols_to_search': ['element_id'],
                                'html': 'event_display_grid.html', 
                                'title': 'APA/CRP {sub_option} Grid'
                            },
                             'plane': {
                                'cols_to_search': ['plane'],
                                'html': 'event_display_plane.html',
                                'title': 'Plane {sub_option} Grid'
                            }
            }
        },
        'pds': {
            'directory': 'pds_plots',
            'regex': r"run(?P<run>\d+)_(?P<trigger>\d+)_([^_]+)\.svg",
            'views': {
                'pds': {
                        'html': 'pds.html',
                        'title': 'PDS Plots'
                }
            },
            'title': 'PDS'
        },
        'tests_wibs': {
            'directory': 'WIBTests',
            'regex': r"Tests_WIBS_results_run(?P<run>\d+)_trigger(?P<trigger>\d+)\.[^.]+",
            'views': {
                'tests_wibs': {
                    'html': 'tests_wibs.html',
                    'title': 'TPC WIB Test Results'
                }
            },
           'title': 'WIB Tests'
        },
    }

    def __init__(self, config: Optional[dict]=None, common_columns = ['run', 'trigger']):
        ''' Read the display config. Common columns are used across ALL displays
        '''
        self._display_configs = []
        if config is None:
            self._global_config = self.CONFIG_DICT
        else:
            self._global_config = config
            
        
        self._common_cols = common_columns
        self._displays_list = self.make_display_conf()
        
    @property
    def common_columns(self):
        return self._common_cols
    
    def make_display_conf(self)->List[DisplayData]:
        '''Make our display config'''
        for disp_name, disp_opts in self._global_config.items():
            # Set up displays first
            
            # Now get default display
            views = disp_opts.get('views', None)
            if views is None:
                    raise KeyError("Could not find views in config dict! This is required")

            views_list = self.make_views_list(views)
            
            cols_to_show = self._common_cols + disp_opts.get('all_columns_to_show', [])
            
            disp_data = DisplayData(
                name= disp_name,
                subdirectory=disp_opts.get('directory', '',),
                views=views_list,
                all_columns_to_show=cols_to_show,
                regex=disp_opts.get('regex', ""),
                title=disp_opts.get('title', disp_name)
            )
            
            self._display_configs.append(disp_data)
            
        return self._display_configs

    def make_views_list(self, views: dict)->List[ViewData]:
        '''Make list of views '''
        views_list = []
        
        for view_name, view_opts in views.items():

            # Convert to the display name            
            view_data = ViewData(
                name=view_name,
                html=view_opts.get('html',""),
                cols_to_search=view_opts.get('cols_to_search', []),
                title = view_opts.get('title', view_name)
            )

            views_list.append(view_data)
        return views_list

    @property
    def displays_list(self)->List[DisplayData]:
        return self._displays_list