from pathlib import Path
from typing import Optional

from flask import Flask

from dqmdisplay.file_operations.app_manager import AppManager
from dqmdisplay.file_operations.file_database import DQMImageDatabase, DQMImageDatabaseCollection
from dqmdisplay.file_operations.dqm_config import DisplayConfig, DisplayData
from dqmdisplay.file_operations.dqm_plot_navigator import DQMPlotNavigator


class DQMDisplayApp:
    '''
    Main application class for DQM display functionality.
    Manages database collections, displays, and navigation.
    '''
    
    def __init__(self, base_directory: str | Path, config_dict: Optional[dict] = None):
        self._base_directory = Path(base_directory)
        
        # Configure the display system
        self._config = DisplayConfig(config_dict)
        
        # Initialize the main database collection
        self._database_collection = DQMImageDatabaseCollection()
        
        # Initialize the plot navigator
        self._navigator = None
        
        # Set up all displays and databases
        self._initialize_displays()
        self._initialize_navigator()
    
    @property
    def config(self) -> DisplayConfig:
        """Get the display configuration"""
        return self._config
    
    @property
    def database_collection(self) -> DQMImageDatabaseCollection:
        """Get the database collection"""
        return self._database_collection
    
    @property  
    def navigator(self) -> DQMPlotNavigator:
        """Get the plot navigator"""
        return self._navigator
    
    def _initialize_displays(self):
        '''Set up all display databases and views'''
        for display_data in self._config.displays_list:
            # Create the database for this display
            database = DQMImageDatabase(
                directory=self._base_directory,
                subdir=display_data.subdirectory,
                name=display_data.name,
                regex=display_data.regex,
                additional_elements=display_data.all_columns_to_show[len(self._config.common_columns):]
            )
            
            # Add to collection
            self._database_collection.add_display(database)
            
            # Add all views for this display
            for view_data in display_data.views:
                # Get the search column (currently limited to 1)
                search_col = view_data.cols_to_search[0] if view_data.cols_to_search else None
                self._database_collection.add_view(view_data.name, display_data.name, search_col)
    
    def _initialize_navigator(self):
        '''Initialize the plot navigator with default styling'''
        self._navigator = DQMPlotNavigator(
            database_collection=self._database_collection,
            config=self._config
        )
        
        # You can customize styling here if needed
        # self._navigator.add_display_styling('custom_display', 'info', 'custom-icon', 'Custom Display')
    
    def add_display_to_app(self, app: Flask, display_data: DisplayData):
        '''Add routing for a single display to the Flask app'''
        # Get the database for this display
        database = self._database_collection.get_display(display_data.name)
        if database is None:
            raise ValueError(f"No database exists for {display_data.name}")
        
        # Add routes for all views of this display
        for view_data in display_data.views:            
            manager = AppManager(
                database=database,
                html_path=view_data.html,
                additional_column_list=view_data.cols_to_search,
                default_cols=self._config.common_columns,
                view_name=view_data.name
            )
            
            # Add to Flask app
            manager.add_to_app(app)
    
    def link_app(self, app: Flask):
        '''Link all displays and navigator to the Flask application'''
        # Add all display routes
        for display_data in self._config.displays_list:
            self.add_display_to_app(app, display_data)
        
        # Add the plot navigator
        self._navigator.add_to_app(app)
    
    def refresh_data(self):
        '''Refresh cached data (useful when files change)'''
        # Invalidate navigator cache
        if self._navigator:
            self._navigator.invalidate_cache()
        
        # Could also refresh database data here if needed
        # For now, databases are built at initialization time
    
    def add_custom_navigator_styling(self, display_name: str = None, view_name: str = None, **kwargs):
        '''Add custom styling to the navigator'''
        if display_name and self._navigator:
            self._navigator.add_display_styling(display_name, **kwargs)
        
        if view_name and self._navigator:
            self._navigator.add_view_styling(view_name, **kwargs)