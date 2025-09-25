from flask import Flask, render_template, jsonify, url_for
from typing import Dict, Any
import pandas as pd
import logging
from dqmdisplay.file_operations.file_database import DQMImageDatabaseCollection
from dqmdisplay.file_operations.dqm_config import DisplayConfig
from dqmdisplay.file_operations.app_manager import RouteMaker


class DQMPlotNavigator:
    """
    Creates a navigation page for exploring available plots organized by run and trigger,
    with lazy loading for runs and triggers.
    """

    def __init__(self, database_collection: DQMImageDatabaseCollection, display_config: DisplayConfig):
        logging.info("Making DQMPlotNavigator")
        self.database_collection = database_collection
        self.display_config = display_config

        # Build routes for each view
        self.route_makers: Dict[str, RouteMaker] = {}
        for view_name, view_opts in database_collection.get_all_views().items():
            self.route_makers[view_name] = RouteMaker(
                view_name,
                self.database_collection.get_display_for_view(view_name),
                [view_opts.get('page_col_name')],
                display_config.common_columns
            )

        self._view_title_lookup = self._build_view_title_lookup()

    def _build_view_title_lookup(self) -> Dict[str, str]:
        title_lookup = {}
        for display in self.display_config.displays_list:
            for view in display.views:
                title_lookup[view.name] = view.title
        return title_lookup

    def _get_view_display_name(self, view_name: str, extra_params: Dict[str, Any]) -> str:
        title_template = self._view_title_lookup.get(view_name, view_name.replace('_', ' ').title())

        # Handle {sub_option} replacement
        if '{sub_option}' in title_template:
            if extra_params:
                sub_option = str(list(extra_params.values())[0])
                display_name = title_template.replace('{sub_option}', sub_option)
            else:
                display_name = title_template.replace(' {sub_option}', '').replace('{sub_option}', '')
        else:
            display_name = title_template

        # Append additional params if any
        if len(extra_params) > 1:
            param_str = ', '.join([f"{k.title()}: {v}" for k, v in list(extra_params.items())[1:]])
            display_name += f" ({param_str})"
        elif len(extra_params) == 1 and '{sub_option}' not in title_template:
            param_str = ', '.join([f"{k.title()}: {v}" for k, v in extra_params.items()])
            display_name += f" ({param_str})"

        return display_name

    def add_to_app(self, app: Flask):
        # Main navigator page
        app.add_url_rule('/plot_navigator', 'plot_navigator', self.render_navigator_page)

        # JSON endpoints for lazy loading
        app.add_url_rule('/plot_navigator_runs', 'plot_navigator_runs', self.get_runs_json)
        app.add_url_rule('/plot_navigator_triggers/<int:run>', 'plot_navigator_triggers', self.get_triggers_json)

    # -----------------------------
    # JSON endpoints for AJAX
    # -----------------------------
    def get_runs_json(self):
        """Return a list of runs"""
        df_runs = self.database_collection.get_unique_cols_all_db(['run'])
        sorted_runs = sorted(df_runs['run'], reverse=True)
        return jsonify({"runs": sorted_runs})

    def get_triggers_json(self, run: int):
        """Return triggers and plots for a given run, handling extra columns correctly"""
        df = self.database_collection.get_existing_combos()
        
        df_run = df[df['run'] == run]

        triggers_data = []

        # Group by trigger
        for trigger, trigger_group in df_run.groupby('trigger'):
            plots = []

            # Further group by view_name to handle multiple extra column values
            for view_name, view_group in trigger_group.groupby('view_name'):
                opts = self.database_collection.get_view(view_name)
                col_name = opts.get("page_col_name")

                # If there's an extra column, get all unique values; else just [None]
                if col_name:
                    unique_vals = view_group[col_name].unique()
                else:
                    unique_vals = [None]

                # Build plot entries for each unique extra value
                for val in unique_vals:
                    extra_params = {}
                    if col_name:
                        # Convert to int if possible
                        if isinstance(val, (pd.Series, pd.Index)):
                            val = val.item()
                        extra_params[col_name] = int(val)

                    # Build URL safely
                    try:
                        plot_url = url_for(
                            self.route_makers[view_name].page_name(),
                            run=int(run),
                            trigger=int(trigger),
                            **extra_params
                        )
                    except Exception:
                        plot_url = "#"

                    plots.append({
                        "name": view_name,
                        "display_name": self._get_view_display_name(view_name, extra_params),
                        "url": plot_url,
                        "params": extra_params
                    })

            triggers_data.append({
                "trigger": int(trigger) if isinstance(trigger, (int, float, pd.Series, pd.Index)) else trigger,
                "plots": plots
            })

        return jsonify({"triggers": triggers_data})


    # -----------------------------
    # Main navigator page
    # -----------------------------
    def render_navigator_page(self):
        """
        Render the main template (loads only the page skeleton; runs and triggers
        are loaded via AJAX)
        """
        return render_template('plot_navigator.html')
