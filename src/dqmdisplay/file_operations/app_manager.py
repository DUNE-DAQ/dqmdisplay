# class PlotAvailability(NamedTuple):
#     """Simple data structure to track what plots are available for a run/trigger"""
#     event_display: bool
#     wib_tests: bool  
#     pds: bool


from dqmdisplay.file_operations.file_database import DQMImageDatabase
from flask import Flask, render_template, url_for


from typing import List


class AppManager():
    def __init__(self,
                 view_name: str,
                 database: DQMImageDatabase,
                 html_path: str,
                 additional_column_list: List[str] = [],
                 default_cols: List[str] = ['run', 'trigger']
                ):

        # Set up prefix/suffix
        self._view_name = view_name
        self._html_path = html_path
        self._database = database
        self._additional_columnn_list = additional_column_list
        self._full_column_list = default_cols + additional_column_list


    @classmethod
    def __list_to_path(cls, l: List[str]):
        return "".join(f"/{p}<{p}>" for p in l)

    def page_name(self):
        if self._database.name == self._view_name:
            return self._view_name
        
        return f"{self._database.name}_{self._view_name}"

    def __to_url(self,  l: List[str]):
        return f"/{self.page_name()}{self.__list_to_path(l)}"

    @property
    def latest_url(self):
        return self.__to_url(self._additional_columnn_list)+"/latest"

    @property
    def full_url(self):
        return self.__to_url(self._full_column_list)
                

    def _add_image_to_app(self, images, vals):
        '''
        Add a set of images to the app
        '''
        
        if (not images is None) and (not images.empty):
            images = [i.name for i in images[self._database.name]]
        else:
            images = []

        # Next page
        search_args = {k: v for k, v in vals.items() if k not in self._additional_columnn_list}
        
        _, next_args = self._database.get_next(**search_args)
        # Previous page
        _, prev_args = self._database.get_prev(**search_args)

        # Build navigation URLs
        next_url = None
        prev_url = None

        current_det = {k: v for k, v in vals.items() if k in self._additional_columnn_list}

        if next_args and not self._database.get_eq(**current_det, **next_args).empty:
            # Merge the navigation args with current path-specific args
            next_kwargs = {**{k: v for k, v in vals.items() if k in self._additional_columnn_list}, **next_args}
            next_url = url_for(self.page_name(), **next_kwargs)


        if prev_args and not self._database.get_eq(**current_det, **prev_args).empty:
            prev_kwargs = {**{k: v for k, v in vals.items() if k in self._additional_columnn_list}, **prev_args}
            prev_url = url_for(self.page_name(), **prev_kwargs)

        return render_template(self._html_path, images=images,
                             next_url=next_url, prev_url=prev_url,
                             **vals)

    def add_latest_to_app(self, **kwargs):
        images, vals = self._database.get_latest(**kwargs)
        return self._add_image_to_app(images, vals)

    def add_image_to_app(self, **kwargs):
        images = self._database.get_eq(**kwargs)
        return self._add_image_to_app(images, kwargs)    

    def add_to_app(self, app: Flask):        
        app.add_url_rule(self.full_url, self.page_name(), self.add_image_to_app)
        app.add_url_rule(self.latest_url, "latest_"+self.page_name(), self.add_latest_to_app)