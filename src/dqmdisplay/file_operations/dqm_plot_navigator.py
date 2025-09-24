from flask import Flask, request, render_template, jsonify
from functools import lru_cache
from typing import Dict, List, Any

from dqmdisplay.file_operations.dqm_config import DisplayConfig
from dqmdisplay.file_operations.file_database import DQMImageDatabaseCollection


class DQMPlotNavigator:
    """
    Handles the plot navigator functionality for DQM displays.
    Provides a web interface to browse available plots by run/trigger with lazy loading.
    """
    
    def __init__(self, database_collection: DQMImageDatabaseCollection, 
                 config: DisplayConfig, template_name: str = 'plot_navigator.html'):
        self._database_collection = database_collection
        self._config = config
        self._template_name = template_name

    @lru_cache(maxsize=128)  # Increase cache size for run-specific data
    def _get_plot_data(self):
        """Get cached plot data from the database collection"""
        return self._database_collection.get_unique_as_dict(self._config.common_columns)

    @lru_cache(maxsize=1)
    def _get_display_config(self) -> Dict[str, Any]:
        """Generate display configuration for the navigator template"""
        display_config = {}
        
        # Iterate through all displays in the config
        for display_data in self._config.displays_list:
            display_name = display_data.name
            
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
        per_page = int(request.args.get('per_page', 20))
        per_page_options = [10, 20, 50, 100]
        
        if per_page not in per_page_options:
            per_page = 20
            
        return page, per_page, per_page_options

    @lru_cache(maxsize=1)
    def _get_run_summaries_fast(self) -> List[Dict]:
        """Get run summaries without computing full existence data - much faster"""
        # Just get unique combinations without existence checks
        unique_combos = self._database_collection.get_unique_cols_all_db(self._config.common_columns)
        
        if unique_combos.empty:
            return []
            
        # Group by run and count triggers
        run_groups = unique_combos.groupby('run')
        run_summaries = []
        
        for run, group in run_groups:
            trigger_count = len(group)
            # Estimate plot count based on triggers and available displays
            # This is faster than computing exact existence
            estimated_plots = trigger_count * len(self._config.displays_list)
            
            run_summaries.append({
                'run': run,
                'trigger_count': trigger_count,
                'plot_count': estimated_plots  # Rough estimate for speed
            })
        
        # Sort runs in descending order
        run_summaries.sort(key=lambda x: x['run'], reverse=True)
        return run_summaries

    def _build_run_summary(self, run_trigger_data: Dict) -> List[Dict]:
        """Build run summary data for lazy loading"""
        run_summaries = []
        
        for run in sorted(run_trigger_data.keys(), reverse=True):
            trigger_dict = run_trigger_data[run]
            trigger_count = len(trigger_dict)
            
            # Count available plots across all triggers for this run
            total_plots = 0
            for trigger_data in trigger_dict.values():
                exists = trigger_data.get('exists', {})
                for availability in exists.values():
                    if isinstance(availability, bool):
                        if availability:
                            total_plots += 1
                    elif isinstance(availability, dict):
                        total_plots += sum(1 for v in availability.values() if v)
            
            run_summaries.append({
                'run': run,
                'trigger_count': trigger_count,
                'plot_count': total_plots
            })
        
        return run_summaries

    def _build_trigger_data(self, run_trigger_data: Dict, run: int) -> List[Dict]:
        """Build trigger data for a specific run - used for AJAX loading"""
        trigger_dict = run_trigger_data.get(run, {})
        triggers = []
        
        for trigger in sorted(trigger_dict.keys(), reverse=True):
            trigger_data = trigger_dict[trigger]
            availability = trigger_data.get('exists', {})
            
            # Build plot list for this trigger
            plots = []
            for display_name, display_availability in availability.items():
                display_info = None
                for display_data in self._config.displays_list:
                    if display_data.name == display_name:
                        display_info = display_data
                        break
                
                if not display_info:
                    continue
                    
                if isinstance(display_availability, bool):
                    if display_availability:
                        for view_data in display_info.views:
                            plots.append({
                                'display': display_info.title,
                                'view_name': view_data.name,
                                'title': view_data.title,
                                'url_params': {
                                    'run': run,
                                    'trigger': trigger
                                }
                            })
                elif isinstance(display_availability, dict):
                    for sub_option, is_available in display_availability.items():
                        if is_available:
                            for view_data in display_info.views:
                                if view_data.cols_to_search:
                                    sub_param = view_data.cols_to_search[0]
                                    plots.append({
                                        'display': display_info.title,
                                        'view_name': view_data.name,
                                        'title': view_data.title.replace('{sub_option}', str(sub_option)),
                                        'url_params': {
                                            'run': run,
                                            'trigger': trigger,
                                            sub_param: sub_option
                                        }
                                    })
            
            triggers.append({
                'trigger': trigger,
                'plot_count': len(plots),
                'plots': plots
            })
        
        return triggers

    def get_trigger_data(self, run: int):
        """AJAX endpoint to get trigger data for a specific run"""
        try:
            run_trigger_data = self._get_plot_data()
            triggers = self._build_trigger_data(run_trigger_data, run)
            display_config = self._get_display_config()
            
            return jsonify({
                'success': True,
                'triggers': triggers,
                'display_config': display_config
            })
        except (KeyError, ValueError, TypeError) as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })

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
        
        # Use fast summary instead of full data for initial load
        try:
            all_run_summaries = self._get_run_summaries_fast()
        except (AttributeError, KeyError, ValueError):
            # Fallback to slow method if fast method fails
            run_trigger_data = self._get_plot_data()
            if not run_trigger_data:
                return render_template(self._template_name, 
                                     run_summaries=[],
                                     display_config={},
                                     **self._calculate_pagination_info(1, 0, per_page))
            all_run_summaries = self._build_run_summary(run_trigger_data)
        
        total_entries = len(all_run_summaries)
        
        # Calculate pagination
        pagination_info = self._calculate_pagination_info(page, total_entries, per_page)
        
        # Only process runs for current page
        start_idx = (pagination_info['current_page'] - 1) * per_page
        end_idx = start_idx + per_page
        current_page_summaries = all_run_summaries[start_idx:end_idx]
        
        # Generate display configuration dynamically
        display_config = self._get_display_config()
        
        return render_template(self._template_name, 
                              run_summaries=current_page_summaries,
                              display_config=display_config,
                              per_page=per_page,
                              per_page_options=per_page_options,
                              **pagination_info)

    def add_to_app(self, app: Flask, url_rule: str = '/navigator', endpoint: str = 'plot_navigator'):
        """Add the plot navigator to a Flask application"""
        app.add_url_rule(url_rule, endpoint, self.render_navigator)
        app.add_url_rule(f'{url_rule}/triggers/<int:run>', f'{endpoint}_triggers', 
                        self.get_trigger_data)

    def invalidate_cache(self):
        """Invalidate all cached data (useful when data changes)"""
        self._get_plot_data.cache_clear()
        self._get_run_summaries_fast.cache_clear()
        self._get_display_config.cache_clear()