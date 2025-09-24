# class PlotAvailability(NamedTuple):
#     """Simple data structure to track what plots are available for a run/trigger"""
#     event_display: bool
#     wib_tests: bool  
#     pds: bool


from dqmdisplay.file_operations.file_database import DQMImageDatabase
from flask import Flask, render_template, url_for


from typing import List


class AppManager():
    def __init__(self, database: DQMImageDatabase,
                 html_path: str,
                 additional_column_list: List[str] = [],
                 default_cols: List[str] = ['run', 'trigger']
                 ):

        # Set up prefix/suffix
        self._html_path = html_path
        self._database = database
        self._additional_columnn_list = additional_column_list
        self._full_column_list = default_cols + additional_column_list

    @property
    def endpoint(self):
        return f"{self._database.name}"

    @classmethod
    def __list_to_path(cls, l: List[str]):
        return "".join(f"/{p}<{p}>" for p in l)


    def __to_url(self, l: List[str]):
        return f"/{self._database.name}{self.__list_to_path(l)}"

    @property
    def latest_url(self):
        return self.__to_url(self._additional_columnn_list)+"/latest"

    @property
    def full_url(self):
        return self.__to_url(self._full_column_list)

    def get_images_vals(self, **kwargs):
        images = self._database.get_eq(**kwargs)
        vals = kwargs
        return images, vals
                

    def _add_image_to_app(self, images, vals):
        '''
        Add a set of images to the app
        '''
        
        if (not images is None) and (not images.empty):
            images = [i.name for i in images[self._database.name]]
        else:
            images = []

        # Next page
        _, next_args = self._database.get_next(**{k: v for k, v in vals.items()})
        # Previous page
        _, prev_args = self._database.get_prev(**{k: v for k, v in vals.items()})

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

    def add_latest_to_app(self, **kwargs):
        images, vals = self._database.get_latest(**kwargs)

        return self._add_image_to_app(images, vals, **kwargs)

    def add_image_to_app(self, **kwargs):
        images = self._database.get_eq(**kwargs)
        vals = kwargs

        return self._add_image_to_app(images, vals)    

    def add_to_app(self, app: Flask):
        app.add_url_rule(self.full_url, self.endpoint, self.add_image_to_app)
        app.add_url_rule(self.latest_url, self.endpoint, self.add_latest_to_app)