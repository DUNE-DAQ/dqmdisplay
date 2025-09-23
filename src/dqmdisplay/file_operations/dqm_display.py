from pathlib import Path
from typing import List, Optional, NamedTuple
from functools import lru_cache

from flask import Flask, render_template, url_for, request

from dqmdisplay.file_operations.file_database import ImageExistsDatabase, DQMImageDatabase

'''
Collection of useful objects for DQM display. For now we'll hard code most of it
'''

# class PlotAvailability(NamedTuple):
#     """Simple data structure to track what plots are available for a run/trigger"""
#     event_display: bool
#     wib_tests: bool  
#     pds: bool


class AppManager():
    def __init__(self, path_list: List[str], database: DQMImageDatabase,
                 html_path: str, name_prefix: Optional[str]=None, name_suffix: Optional[str]=None, latest: bool=False):
        
        # Set up prefix/suffix
        self._name_prefix = name_prefix
        self._name_suffix = name_suffix
        
        self._html_path = html_path
        self._database = database

        self._path_list = path_list
        self._latest=latest

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
        
        return "".join(f"/{p}:<{p}>" for p in self._path_list)

    @property
    def db_url(self):
        full_path = f"/{self._database.name}{self.name_suffix}{self.data_path}"
        if self._name_prefix is not None:
            full_path = f"{full_path}/{self._name_prefix}"

        return full_path
    
    def add_image_to_app(self, **kwargs):

        if self._latest:
            images, vals = self._database.dataframe.get_latest(**kwargs)
        else:
            images = self._database.dataframe.get_eq(**kwargs)
            vals = kwargs
        
        
        if (not images is None) and (not images.empty):
            images = [i.name for i in images[self._database.name]]
        else:
            images = []

        _, next_args = self._database.dataframe.get_next(**{k: v for k, v in vals.items() if k in ['run', 'trigger']})
        _, prev_args = self._database.dataframe.get_prev(**{k: v for k, v in vals.items() if k in ['run', 'trigger']})
        
        # Build navigation URLs
        next_url = None
        prev_url = None
        
        if next_args:
            # Merge the navigation args with current path-specific args
            next_kwargs = {**{k: v for k, v in vals.items() if k not in ['run', 'trigger']}, **next_args}
            next_url = url_for(self.endpoint, **next_kwargs)
            
        if prev_args:
            prev_kwargs = {**{k: v for k, v in vals.items() if k not in ['run', 'trigger']}, **prev_args}
            prev_url = url_for(self.endpoint, **prev_kwargs)
        
        return render_template(self._html_path, images=images, 
                             next_url=next_url, prev_url=prev_url, 
                             **vals)
    
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
    
    def __init__(self, base_directory: str | Path, config_dict: Optional[dict]=None):
        self._base_directory = Path(base_directory)
        
        if config_dict is None:
            self._config_dict = self.CONFIG_DICT
        else:
            self._config_dict = config_dict
        
        db_list = []        
        for name, opts in self._config_dict.items():            
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
        
        opts = self._config_dict.get(db_name, None)
        
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
        AppManager(cols, db, opts.get('html',''), 'latest', latest=True)(app)
        
        # Now we add the additional pages
        if not (extras:=opts.get('extra_views', None)):
            return
        
        for extra_name, extra_opts in extras.items():
            # We're going to make a single extra path
            extra_path = self.MERGE_ON + extra_opts.get('additional_cols', [])
            # Add to the app
            AppManager(extra_path, db, opts.get('html',''), name_suffix=extra_name)(app)
            # Add latest to the app
            AppManager(extra_opts.get('additional_cols', []), db, opts.get('html',''), name_prefix='latest', name_suffix=extra_name, latest=True)(app)

    @lru_cache(maxsize=1)
    def _get_plot_navigator_data(self):
        """Cached method to get the raw plot availability data"""
        df = self._main_database.as_navigable().as_dataframe()
        
        if df.empty:
            return {}
        
        # Group by run and trigger more efficiently
        run_trigger_data = {}
        
        # Use groupby for better performance
        grouped = df.groupby(['run', 'trigger'])
        
        for (run, trigger), _ in grouped:
            run = int(run)
            trigger = int(trigger)
            
            if run not in run_trigger_data:
                run_trigger_data[run] = {}
            
            run_trigger_data[run][trigger] = {}
            
            # Actually check if each plot type has data by looking at the specific columns
            # The database columns should contain boolean values or counts indicating availability

            check = self._main_database.check_has_col(**{'run': run, 'trigger': trigger})

            for n in self._main_database.database_names: 
                run_trigger_data[run][trigger][n] = check[n]
        
        # Sort runs and triggers in descending order
        sorted_data = {}
        for run in sorted(run_trigger_data.keys(), reverse=True):
            sorted_data[run] = dict(sorted(run_trigger_data[run].items(), reverse=True))
        
        return sorted_data


    def add_plot_navigator(self):
        """Fast plot navigator that uses cached data computation with pagination"""
        run_trigger_data = self._get_plot_navigator_data()
        
        # Get pagination parameters from request
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))  # Default 20 entries per page
        
        # Available per_page options
        per_page_options = [10, 20, 50, 100]
        if per_page not in per_page_options:
            per_page = 20  # Default fallback
        
        # Flatten the data into a list for pagination
        all_entries = []
        for run in sorted(run_trigger_data.keys(), reverse=True):
            for trigger in sorted(run_trigger_data[run].keys(), reverse=True):
                all_entries.append({
                    'run': run,
                    'trigger': trigger,
                    'availability': run_trigger_data[run][trigger]
                })
        
        # Calculate pagination
        total_entries = len(all_entries)
        total_pages = (total_entries + per_page - 1) // per_page  # Ceiling division
        
        # Ensure page is within valid range
        page = max(1, min(page, total_pages))
        
        # Get entries for current page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_entries = all_entries[start_idx:end_idx]
        
        # Calculate pagination info
        has_prev = page > 1
        has_next = page < total_pages
        prev_page = page - 1 if has_prev else None
        next_page = page + 1 if has_next else None
        
        # Generate page range for pagination controls (show up to 5 pages around current)
        page_range_start = max(1, page - 2)
        page_range_end = min(total_pages, page + 2)
        page_range = list(range(page_range_start, page_range_end + 1))
        
        return render_template('plot_navigator.html', 
                            page_entries=page_entries,
                            current_page=page,
                            total_pages=total_pages,
                            total_entries=total_entries,
                            per_page=per_page,
                            per_page_options=per_page_options,
                            has_prev=has_prev,
                            has_next=has_next,
                            prev_page=prev_page,
                            next_page=next_page,
                            page_range=page_range)

    
    def link_app(self, app: Flask):
        '''
        Slightly over complicated wrapper for dynamically generating flask app routes
        '''    
        for db_name in self._config_dict.keys():
            # Now we route      
            self.add_db_opt(app, db_name)      
        
        # Add the simplified plot navigator
        app.add_url_rule('/navigator', 'plot_navigator', self.add_plot_navigator)