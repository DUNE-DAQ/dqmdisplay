from pathlib import Path
from typing import Optional
from functools import lru_cache

from flask import Flask, request, render_template

from dqmdisplay.file_operations.app_manager import AppManager
from dqmdisplay.file_operations.file_database import DQMImageDatabase, DQMImageDatabaseCollection
from dqmdisplay.file_operations.dqm_config import DisplayConfig, DisplayData
'''
Collection of useful objects for DQM display. For now we'll hard code most of it
'''


class DQMDisplayApp:
    '''
    Actual code to link to a Flask application
    '''
    
    def __init__(self, base_directory: str | Path, config_dict: Optional[dict]=None):
        self._base_directory = Path(base_directory)
        
        # We can now configure stuff... yay
        self._config = DisplayConfig(config_dict)
        
        # Add main database
        self._main_database = DQMImageDatabaseCollection()
        
        # Initialise it
        self._initialise_display()    
            
    def _initialise_display(self):
        '''
        Set up main display
        '''
        for disp in self._config.displays_list:
            # Make the display            
            db = DQMImageDatabase(self._base_directory,
                                  disp.subdirectory,
                                  disp.name,
                                  disp.regex,
                                  disp.all_columns_to_show)
            
            self._main_database.add_display(db)
            
            # Now we can add in the views
            for view in disp.views:
                # HACK: Currently can only have 1 non-default column!
                if view.cols_to_search:
                    col_to_search = view.cols_to_search[0]
                else:
                    col_to_search = None
                
                self._main_database.add_view(view.name, disp.name, col_to_search)
            
    def add_display_to_app(self, app: Flask, display_data: DisplayData):
        '''
        Adds the image options for a single database
        '''
        
        # Get the main display
        display_image_db = self._main_database.get_display(display_data.name)
        if display_image_db is None:
            raise Exception(f"No database exists for {display_data.name}")
        
        # Now we can add the things we actually want to see
        for view in display_data.views:            
            manager = AppManager(display_image_db, 
                                 view.html,
                                 view.cols_to_search,
                                 self._config.common_columns)
            
            # Now we need to link it to the Flask application
            manager.add_to_app(app)
    
    @lru_cache(maxsize=1)
    def _get_plot_navigator_data(self):
        ''' Gets the data for the navigator
        '''
        return self._main_database.get_unique_as_dict(self._config.common_columns)
    

    def add_plot_navigator(self):
        """Plug into the plot navigator
        NOTE: THIS IS HARDCODED TO USE RUNS, TRIGGERS ANYTHING ELSE WILL BREAK IT!
        
        """
        # Get pagination parameters first to avoid processing unnecessary data
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))  # Increased default for fewer requests
        per_page_options = [20, 50, 100, 200]
        
        if per_page not in per_page_options:
            per_page = 50
        
        # Get cached data
        run_trigger_data = self._get_plot_navigator_data()
        
        if not run_trigger_data:
            return render_template('plot_navigator.html', page_entries=[])
        
        # Pre-sort runs for efficiency
        sorted_runs = sorted(run_trigger_data.keys(), reverse=True)
        total_entries = len(sorted_runs)
        total_pages = (total_entries + per_page - 1) // per_page
        
        # Validate and clamp page
        page = max(1, min(page, total_pages))
        
        # Only process runs for current page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        current_page_runs = sorted_runs[start_idx:end_idx]
        
        # Build minimal data structure for current page only
        page_entries = []
        for run in current_page_runs:
            # Sort triggers once
            sorted_triggers = sorted(run_trigger_data[run].keys(), reverse=True)
            triggers = [{
                'trigger': trigger,
                'availability': run_trigger_data[run][trigger]
            } for trigger in sorted_triggers]
            
            page_entries.append({
                'run': run,
                'triggers': triggers
            })
        
        # Pagination info
        has_prev = page > 1
        has_next = page < total_pages
        prev_page = page - 1 if has_prev else None
        next_page = page + 1 if has_next else None
        
        # Optimized page range (fewer buttons for better UX)
        page_range_start = max(1, page - 3)
        page_range_end = min(total_pages, page + 3)
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
    # def link_app(self, app: Flask):
    #     '''
    #     Slightly over complicated wrapper for dynamically generating flask app routes
    #     '''    
    #     for db_name in self._config_dict.keys():
    #         # Now we route      
    #         self.add_db_opt(app, db_name)      
        
    #     # Add the simplified plot navigator
    #     app.add_url_rule('/navigator', 'plot_navigator', self.add_plot_navigator)