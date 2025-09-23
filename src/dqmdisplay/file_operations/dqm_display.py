from pathlib import Path
from typing import List, Optional, NamedTuple
from functools import lru_cache

from flask import Flask, render_template, url_for

from dqmdisplay.file_operations.file_database import ImageExistsDatabase, DQMImageDatabase

'''
Collection of useful objects for DQM display. For now we'll hard code most of it
'''

class PlotAvailability(NamedTuple):
    """Simple data structure to track what plots are available for a run/trigger"""
    event_display: bool
    wib_tests: bool  
    pds: bool


class AppManager():
    def __init__(self, path_list: List[str], database: DQMImageDatabase,
                 html_path: str, name_prefix: Optional[str]=None, name_suffix: Optional[str]=None):
        
        # Set up prefix/suffix
        self._name_prefix = name_prefix
        self._name_suffix = name_suffix
        
        self._html_path = html_path
        self._database = database

        self._path_list = path_list

    @property
    def name_prefix(self):
        return f"{self._name_prefix}_" if self._name_prefix is not None else ""
        
    @property
    def name_suffix(self):
        return f"_{self._name_suffix}" if self._name_suffix is not None else ""

    @property
    def endpoint(self):
        return f"{self.name_prefix}{self._database.name}{self.name_suffix}"
    
    @property
    def data_path(self):
        if not self._path_list:
            return ""
        
        "".join(f"/{p}:<{p}>" for p in self._path_list)

    @property
    def db_url(self):
        full_path = f"/{self._database.name}{self.name_suffix}{self.data_path}"
        if self._name_prefix is not None:
            full_path = f"{full_path}/{self._name_prefix}"
            
        print(full_path)
        return full_path
    
    def add_image_to_app(self, **kwargs):
        images = self._database.dataframe.get_eq(**kwargs)
        if not images.empty:
            images = [i.name for i in images[self._database.name]]
        else:
            images = []

        _, next_args = self._database.dataframe.get_next(**{k: v for k, v in kwargs.items() if k in ['run', 'trigger']})
        _, prev_args = self._database.dataframe.get_prev(**{k: v for k, v in kwargs.items() if k in ['run', 'trigger']})
        
        # Build navigation URLs
        next_url = None
        prev_url = None
        
        if next_args:
            # Merge the navigation args with current path-specific args
            next_kwargs = {**{k: v for k, v in kwargs.items() if k not in ['run', 'trigger']}, **next_args}
            next_url = url_for(self.endpoint, **next_kwargs)
            
        if prev_args:
            prev_kwargs = {**{k: v for k, v in kwargs.items() if k not in ['run', 'trigger']}, **prev_args}
            prev_url = url_for(self.endpoint, **prev_kwargs)
        
        return render_template(self._html_path, images=images, 
                             next_url=next_url, prev_url=prev_url, 
                             **kwargs)
    
    def __call__(self, app: Flask):
        app.add_url_rule(self.db_url, self.endpoint, self.add_image_to_app)


class DQMDisplay:
    '''
    DQM display
    '''
    
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
            'additional_cols': ['element_id', 'plane'],
            'default_cols': ['element_id'],
            'html': 'event_display.html',
            
            # Other views {view_name: options to add} (does nothing rn, this is hardcoded later...)
            'extra_views':  {'grid': {
                                'additional_cols': ['element_id'],
                                'html': 'event_display_grid.html'    
                            },
                             'plane': {
                                'additional_cols': ['plane'],
                                'html': 'event_display_plane.html'
                            }
            }
        },
        'pds': {
            'directory': 'pds_plots',
            'regex': r"run(?P<run>\d+)_(?P<trigger>\d+)_([^_]+)\.svg",
            'html': 'pds.html'
        },
        'tests_wibs': {
            'directory': 'WIBTests',
            'regex': r"Tests_WIBS_results_run(?P<run>\d+)_trigger(?P<trigger>\d+)\.[^.]+",
            'html': 'tests_wibs.html'
        }
    }
    MERGE_ON = ['run', 'trigger']
    
    def __init__(self, base_directory: str | Path):
        self._base_directory = Path(base_directory)
        
        db_list = []        
        for name, opts in self.CONFIG_DICT.items():            
            db = DQMImageDatabase(self._base_directory, opts.get('directory', ''),
                                  name, opts.get('regex'), opts.get('additional_cols', None))
            db_list.append(db)
            
        # Now we have our main lookup make the big database
        self._main_database = ImageExistsDatabase(db_list, self.MERGE_ON)
        
    @property
    def database(self):
        return self._main_database
    
    def add_db_opt(self, app: Flask, db_name: str):
        '''
        Adds the image options for a single database
        '''
        
        opts = self.CONFIG_DICT.get(db_name, None)
        
        if opts is None:
            raise ValueError(f"Cannot find {db_name} in configuration")
        
        db = self._main_database.get_database(db_name)
        if db is None:
            raise ValueError(f"Database: {db_name} not initialised")
    
        # Loop over full naemes
        
        if (cols:=opts.get('default_cols', None)) is None:
            cols = opts.get('additional_cols', [])
            
        main_cols = self.MERGE_ON + cols
        
        # Add to the app
        AppManager(main_cols, db, opts.get('html',''))(app)
        # Add latest to the app
        AppManager(cols, db, opts.get('html',''), 'latest')(app)
        
            
        # Now we add the additional pages
        if not (extras:=opts.get('extra_views', None)):
            return
        
        for extra_name, extra_opts in extras.items():
            # We're going to make a single extra path
            extra_path = self.MERGE_ON + extra_opts.get('additional_cols', [])
            # Add to the app
            AppManager(extra_path, db, opts.get('html',''), extra_name)(app)
            # Add latest to the app
            AppManager(extra_opts.get('additional_cols', []), db, opts.get('html',''), 'latest', extra_name)(app)

    @lru_cache(maxsize=1)
    def add_plot_navigator(self):
        df = self._main_database.as_navigable().as_dataframe()
        
        if df.empty:
            return render_template('plot_navigator.html', run_trigger_data={})
        
        # Group by run and create a simplified structure
        run_trigger_data = {}
        
        for _, row in df.iterrows():
            run = int(row['run'])
            trigger = int(row['trigger'])
            
            if run not in run_trigger_data:
                run_trigger_data[run] = {}
            
            # Simplified availability - if event_display exists, all variants exist
            availability = PlotAvailability(
                event_display=bool(row.get('event_display', False)),
                wib_tests=bool(row.get('tests_wibs', False)),
                pds=bool(row.get('pds', False))
            )
            
            run_trigger_data[run][trigger] = availability
        
        # Sort runs in descending order (most recent first)
        run_trigger_data = dict(sorted(run_trigger_data.items(), reverse=True))
        
        # Sort triggers within each run in descending order
        for run in run_trigger_data:
            run_trigger_data[run] = dict(sorted(run_trigger_data[run].items(), reverse=True))
        
        return render_template('plot_navigator.html', run_trigger_data=run_trigger_data)

    
    def link_app(self, app: Flask):
        '''
        Slightly over complicated wrapper for dynamically generating flask app routes
        '''    
        for db_name in self.CONFIG_DICT.keys():
            # Now we route      
            self.add_db_opt(app, db_name)      
        
        # Add the simplified plot navigator
        app.add_url_rule('/navigator', 'plot_navigator', self.add_plot_navigator)