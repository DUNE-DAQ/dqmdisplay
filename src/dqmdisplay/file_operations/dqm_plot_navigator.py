from flask import Flask, request, render_template
from functools import lru_cache
from typing import Dict, List, Any

from dqmdisplay.file_operations.dqm_config import DisplayConfig
from dqmdisplay.file_operations.file_database import DQMImageDatabaseCollection


class DQMPlotNavigator:
    """
    Handles the plot navigator functionality for DQM displays.
    Provides a web interface to browse available plots by run/trigger.
    """
    
    def __init__(self, database_collection: DQMImageDatabaseCollection, 
                 config: DisplayConfig, template_name: str = 'plot_navigator.html'):
        self._database_collection = database_collection
        self._config = config
        self._template_name = template_name

    @lru_cache(maxsize=1)
    def _get_plot_data(self):
        """Get cached plot data from the database collection"""
        return self._database_collection.get_unique_as_dict(self._config.common_columns)

    def _get_display_config(self) -> Dict[str, Any]:
        """Generate display configuration for the navigator template"""
        display_config = {}
        
        # Iterate through all displays in the config
        for display_data in self._config.displays_list:
            display_name = display_data.name
            
            # Get styling info or use defaults
                        
            # Build views configuration
            views = {}
            for view_data in display_data.views:
                view_name = view_data.name
                
                # Check if this view has sub-options (like element_id, plane)
                has_sub_options = len(view_data.cols_to_search) > 0
                

                
                view_config = {
                    'title': view_data.title,
                    'has_sub_options': has_sub_options
                }
                
                if has_sub_options:
                    # Assume first column is the sub-parameter
                    view_config['sub_param'] = view_data.cols_to_search[0]
                
                views[view_name] = view_config
            
            display_config[display_name] = {
                'title': display_data.title,
                'views': views
            }
        
        return display_config

    def _get_pagination_params(self) -> tuple:
        """Extract and validate pagination parameters from request"""
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        per_page_options = [20, 50, 100, 200]
        
        if per_page not in per_page_options:
            per_page = 50
            
        return page, per_page, per_page_options

    def _build_page_entries(self, run_trigger_data: Dict, current_page_runs: List[int]) -> List[Dict]:
        """Build the data structure for the current page"""
        page_entries = []
        
        for run in current_page_runs:
            # Get trigger data for this run
            trigger_dict = run_trigger_data[run]
            
            # Sort triggers and build trigger list
            sorted_triggers = sorted(trigger_dict.keys(), reverse=True)
            triggers = []
            
            for trigger in sorted_triggers:
                # Get the availability data (exists dict from check_exists)
                availability = trigger_dict[trigger]['exists']
                
                triggers.append({
                    'trigger': trigger,
                    'availability': availability
                })
            
            page_entries.append({
                'run': run,
                'triggers': triggers
            })
        
        return page_entries

    def _calculate_pagination_info(self, page: int, total_entries: int, per_page: int) -> Dict[str, Any]:
        """Calculate pagination information"""
        total_pages = (total_entries + per_page - 1) // per_page
        page = max(1, min(page, total_pages))  # Clamp page
        
        has_prev = page > 1
        has_next = page < total_pages
        prev_page = page - 1 if has_prev else None
        next_page = page + 1 if has_next else None
        
        # Page range for navigation
        page_range_start = max(1, page - 3)
        page_range_end = min(total_pages, page + 3)
        page_range = list(range(page_range_start, page_range_end + 1))
        
        return {
            'current_page': page,
            'total_pages': total_pages,
            'total_entries': total_entries,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_page': prev_page,
            'next_page': next_page,
            'page_range': page_range
        }

    def render_navigator(self):
        """Main method to render the plot navigator"""
        # Get pagination parameters
        page, per_page, per_page_options = self._get_pagination_params()
        
        # Get cached data
        run_trigger_data = self._get_plot_data()
        
        if not run_trigger_data:
            return render_template(self._template_name, 
                                 page_entries=[],
                                 display_config={})
        
        # Generate display configuration dynamically
        display_config = self._get_display_config()
        
        # Pre-sort runs for efficiency
        sorted_runs = sorted(run_trigger_data.keys(), reverse=True)
        total_entries = len(sorted_runs)
        
        # Calculate pagination
        pagination_info = self._calculate_pagination_info(page, total_entries, per_page)
        
        # Only process runs for current page
        start_idx = (pagination_info['current_page'] - 1) * per_page
        end_idx = start_idx + per_page
        current_page_runs = sorted_runs[start_idx:end_idx]
        
        # Build data structure for current page
        page_entries = self._build_page_entries(run_trigger_data, current_page_runs)
        
        return render_template(self._template_name, 
                              page_entries=page_entries,
                              display_config=display_config,
                              per_page=per_page,
                              per_page_options=per_page_options,
                              **pagination_info)

    def add_to_app(self, app: Flask, url_rule: str = '/navigator', endpoint: str = 'plot_navigator'):
        """Add the plot navigator to a Flask application"""
        app.add_url_rule(url_rule, endpoint, self.render_navigator)

    def invalidate_cache(self):
        """Invalidate the cached plot data (useful when data changes)"""
        self._get_plot_data.cache_clear()