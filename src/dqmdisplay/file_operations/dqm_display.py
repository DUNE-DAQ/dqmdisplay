from pathlib import Path
from typing import List, Optional, Dict

from flask import Flask, render_template

from dqmdisplay.file_operations.file_database import ImageExistsDatabase, DQMImageDatabase

'''
Collection of useful objects for DQM display. For now we'll hard code most of it
'''

def make_db_url(path_dict: Dict[str, str|int], database: DQMImageDatabase, name_suffix: Optional[str] = None):
    '''helper function to make a database URL
    '''
    name = database.name
    if name_suffix is not None:
        name+=f"_{name_suffix}"
                
    full_path = f"/{name}"+"".join(f"/{p}:{v}" for p, v in path_dict.items())
    print(f"making {full_path}")

    return full_path

def make_endpoint(database: DQMImageDatabase, name_suffix: Optional[str]=None):
    if name_suffix is None:
        name_suffix=""
    else:
        name_suffix = f"_{name_suffix}"

    return f"{database.name+name_suffix}"
    

def add_image_display_app(app: Flask, path_list: List[str], database: DQMImageDatabase, html_path: str,
                     name_suffix: Optional[str] = None):
    ''' Adds to a Flask app
    '''
    
    full_path = make_db_url({p:f"<{p}>" for p in path_list}, database, name_suffix)
    
    endpoint = make_endpoint(database, name_suffix)

    
    def add_to_app(**kwargs):
        images = database.dataframe.get_eq(**kwargs)[database.name]
        if images is not None:
            images = [i.name for i in images[database.name]]
        else:
            images = []
        _, next_args = database.dataframe.get_next(**kwargs)
        _, prev_args = database.dataframe.get_prev(**kwargs)
        return render_template(html_path, images = images, next=next_args, prev=prev_args, **kwargs)

    app.add_url_rule(full_path, endpoint, add_to_app)

def add_latest_to_app(app, path_list: List[str], database: DQMImageDatabase, html_path: str,
                     name_suffix: Optional[str] = None):

    path_list.copy()


    endpoint = f"latest_{make_endpoint(database, name_suffix)}"
    
    full_path = make_db_url({p:f"<{p}>" for p in path_list}, database, name_suffix)
    full_path  += "/latest"
    print(f"Making latest {full_path}, {endpoint}")

    def add_to_app(**kwargs):
        merge_on = ['run', 'trigger']

        # Means we KNOW what latest refers to
        images, vals = database.dataframe.get_latest(merge_on, **kwargs)
        print(images)
        
        
        if images is not None:
            images = [i.name for i in images[database.name]]
        else:
            images = []
        
        _, next_args = database.dataframe.get_next(**vals)
        # Added here despite the fact that we KNOW this will be None
        _, prev_args = database.dataframe.get_prev(**vals)
        return render_template(html_path, images = images, next=next_args, prev=prev_args, **vals)

    app.add_url_rule(full_path, endpoint, add_to_app)


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
    
    def link_app(self, app: Flask):
        '''
        Slightly over complicated wrapper for dynamically generating flask app routes
        '''    
        for db_name in self.CONFIG_DICT.keys():
            # Now we route      
            self.add_db_opt(app, db_name)      
            
    
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
        print(main_cols)
    
        add_image_display_app(app, main_cols, db, opts.get('html',''))
        add_latest_to_app(app, cols, db, opts.get('html',''))
            
        # Now we add the additional pages
        if not (extras:=opts.get('extra_views', None)):
            return
        
        for extra_name, extra_opts in extras.items():
            # We're going to make a single extra path
            extra_path = self.MERGE_ON + extra_opts.get('additional_cols', [])
            add_image_display_app(app, extra_path, db, opts.get('html',''), extra_name)
            add_latest_to_app(app, extra_opts.get('additional_cols', []), db, opts.get('html',''), extra_name)