'''
HW: Organise files in folder into database
'''
import pandas as pd
from typing import List, Optional, Pattern, Tuple, Dict, Any
import re
from pathlib import Path
from dqmdisplay.utils.dict_tools import nested_group

from tqdm import tqdm

def check_cols_in_db(database: pd.DataFrame, col_list: List[str]):
    ''' Helper function for kwargs checking
    '''
    if set(col_list).difference(c:=database.columns):
        raise ValueError(f"Provided {col_list} but columns are {c}")


class NavigableDataframe:
    '''
    Wrapper object to simplify dataframe queries allowing for more natural next/prev operations
    '''
    def __init__(self, dataframe: pd.DataFrame):
        dataframe.sort_values(list(dataframe.columns), ascending=False, inplace=True)
        self._dataframe = dataframe

    def as_dataframe(self)->pd.DataFrame:
        '''Returns the raw pandas dataframe'''
        return self._dataframe

    def get_eq(self, **kwargs)->'pd.DataFrame':
        '''Check if values in dict are equal to kwargs'''
        mask = pd.Series(True, index=self._dataframe.index)

        for col, val in kwargs.items():
            mask &= self._dataframe[col] == int(val)  # "prev" means greater than for sorted ascending

        return self._dataframe[mask]

    def get_unique(self, col: str):
        return self._dataframe[col].unique()

    def get_next(self, **kwargs)->Tuple[pd.DataFrame, Dict[str, int]] | Tuple[None, dict]:
        '''
        Get the prev row(s) from the one satisfying **kwargs
        '''
        return self._get_adjacent(False, **kwargs)

    def get_prev(self, **kwargs)->Tuple[pd.DataFrame, Dict[str, int]] | Tuple[None, dict]:
        '''
        Get the next row(s) from the one satisfying **kwargs
        '''
        return self._get_adjacent(True, **kwargs)


    def _get_adjacent(self, prev: bool, **kwargs):
        mask = pd.Series(True, index=self._dataframe.index)
        # We go back through the mask
        mask_dict = {k: self._dataframe[k]==int(v) for k, v in kwargs.items()}

        key_search = list(mask_dict.keys())
        key_search.reverse()

        # Go backwards through dict
        for k in key_search:
            if prev:
                mask_dict[k] = self._dataframe[k].astype(int)<int(kwargs[k])
            else:
                mask_dict[k] = self._dataframe[k].astype(int)>int(kwargs[k])

            m_copy = pd.Series(True, index=self._dataframe.index)
            for m in mask_dict.values():
                m_copy &= m

            if not self._dataframe[m_copy].empty:
                mask = m_copy
                break
            else:
                mask_dict.pop(k)
        else:
            return None, {}

        adj = self._dataframe[mask]
        kwarg_list = list(kwargs.keys())

        # We now sort (either get the smallest or largest entry)
        sort_adj = adj.sort_values(kwarg_list, inplace=False, ascending=not prev)

        top = sort_adj.iloc[0]
        search_cond = {s: top[s] for s in kwargs.keys()}
        return self.get_eq(**search_cond), search_cond

    def get_latest(self, merge_on = ['run', 'trigger'], **kwargs)->Tuple[pd.DataFrame, Dict[str, Any]] | Tuple[None, dict]:
        '''
        Get the LATEST entries(s) for a given set of columns
        '''
        check_cols_in_db(self._dataframe, list(kwargs.keys()))

        # Sort dataframe
        self._dataframe.sort_values(merge_on+list(kwargs.keys()) , ascending=False, inplace=True)

        cols = self.get_eq(**kwargs)
        if cols.empty:
            return None, {}

        top_col = cols.iloc[0]
        top_vals = {c: top_col[c] for c in merge_on + list(kwargs.keys())}

        # We also return the TOP values to ensure routing is done simply!
        return self.get_eq(**top_vals), top_vals


class DQMImageDatabase(NavigableDataframe):
    '''
    Stores DQM images for event displays
    '''

    def __init__(self, directory: str | Path, subdir: str | Path, name: str,
                 regex: str, additional_elements: Optional[List[str]]=None):
        '''
        Build the database
        '''
        self._search_terms = ['run', 'trigger']
        self._name = name

        search_dict = self.__build_dataframe(directory, subdir, regex, additional_elements)
        super().__init__(search_dict)

    def __build_dataframe(self, directory: str | Path, subdir: str | Path, regex: str,
                          additional_elements: Optional[List[str]]=None):
        '''
        Build the dataframe list
        '''

        regex_search_str = re.compile(regex, re.X)

        if additional_elements is not None:
            self._search_terms.extend(additional_elements)

        search_path = Path(directory) / Path(subdir)

        if not search_path.exists():
            raise FileNotFoundError(f"Couldn't find directory {search_path}")

        # Now we fill our dataframe [start as dictionary for speed]
        search_dict = {n : [] for n in self._search_terms}
        search_dict[self._name] = []

        # Check for matches with regex
        for f in search_path.iterdir():
            self.__build_search_dict(search_dict, f, regex_search_str)

        return pd.DataFrame.from_dict(search_dict)

    def __build_search_dict(self, search_dict: Dict[str, List[int | Path]], file_path: Path, regex_search_str: Pattern[str]):
        '''
        Builds our searchable dictionary of terms
        '''
        match = regex_search_str.match(file_path.name)
        # No match!
        if not match:
            return

        # Add to file
        for s in self._search_terms:
            try:
                search_dict[s].append(int(match[s]))
            except Exception as e:
                raise ValueError(f"Couldn't find {s} when matching {match} to {file_path.name}") from e

        # Append the FULL file name
        search_dict[self._name].append(file_path)

    @property
    def name(self):
        return self._name

class DQMImageDatabaseCollection :
    '''
    Handler to handle all the BASE databases for a DQMDisplay
    '''
    def __init__(self):
        self._displays: Dict[str, DQMImageDatabase] = {}
        self._views = {}

        self._unique_combo_db = None
        self._new_df_added = True

    @property
    def display_names(self):
        return list(self._views.keys())

    def get_display_for_view(self, view_name: str):
        '''
        Get a dataframe
        '''
        return self._displays[self._views[view_name]['display_name']]

    def get_view(self, view_name: str):
        if view_name not in self._views:
            raise ValueError(f"Cannot find {view_name} in {self.display_names}")

        return self._views[view_name]

    def get_display(self, display_name: str):
        return self._displays.get(display_name, None)

    @classmethod
    def get_extra_col_unq(cls, dataframe: DQMImageDatabase, extra_col: Optional[str]=None):
        '''Gets unique values for some extra column
        '''
        if extra_col is None:
            return None

        # We then sort it for ease of lookup
        return dataframe.get_unique(extra_col).copy()


    def add_display(self, new_dataframe: DQMImageDatabase, extra_col: Optional[str]=None):
        '''
        Add dataframe
        '''
        if not isinstance(new_dataframe, DQMImageDatabase):
            raise TypeError(f"Must add an instance of DQMImageDatabase not {type(new_dataframe)}")

        if new_dataframe in self._displays:
            raise ValueError("Cannot add the same dataframe multiple times!")

        self._displays[new_dataframe.name]  = new_dataframe
        self._new_df_added = True


    def add_view(self, view_name: str, dataframe_name: str, extra_col: Optional[str]=None):
        ''' Add subdisplay
        '''
        # We KNOW any dataframe we use will have its name in the displays dict
        if self._displays.get(dataframe_name, None) is None:
            raise KeyError(f"Couldn't find {dataframe_name} in dataframes")

        unq_page_col_indices = self.get_extra_col_unq(self._displays[dataframe_name], extra_col)

        self._views[view_name] = {
            'display_name': dataframe_name,
            'page_col_name': extra_col,
            'page_col_indices': unq_page_col_indices
        }

    def check_exists(self, **kwargs):
        '''
        So now we have our displays dict, we can do this properly!
        '''
        return_dict = {}

        equal_list = {d_name: d.get_eq(**kwargs) for d_name, d in self._displays.items()}

        for display, opts in self._views.items():
            # Not the most efficient since for multiple views we need to do this multiple times
            equal_rows = equal_list[opts['display_name']]

            extra_col = opts['page_col_name']
            if extra_col is None:
                # Here we don't need to deal with any funkyness
                return_dict[display] = not equal_rows.empty
                continue

            extra_col_vals = opts['page_col_indices']

            return_dict[display] = {i: not equal_rows[equal_rows[extra_col]==i].empty for i in extra_col_vals}

        return return_dict

    def get_unique_cols_all_db(self, col_labs: List[str]):
        # More efficient to cache this infomration
        if not self._new_df_added and self._unique_combo_db is not None:
            return self._unique_combo_db

        # First time/if a new object has been added
        concat_obj = pd.concat([d.as_dataframe()[col_labs] for d in self._displays.values()], ignore_index=True)
        self._unique_combo_db = concat_obj.drop_duplicates().reset_index(drop=True)
        self._unique_combo_db.sort_values(col_labs, ascending=False, inplace=True)

        # Means we don't need to regenerate everything from scratch
        self._new_df_added = False

        return self._unique_combo_db

    def get_unique_as_dict(self, col_label: List[str]):
        '''
        Make a nested dictionary of unique information
        '''
        unique_combos = self.get_unique_cols_all_db(col_label)

        if unique_combos.empty:
            return {}

        # Now group
        unique_combo_groups = unique_combos.groupby(col_label)

        exists_data = []

        # Bit hacky, we'll loop over each row like this
        for opts, _ in tqdm(unique_combo_groups):
            opts_dict = {c: o for c, o in zip(col_label, opts)}

            opts_dict['exists'] = self.check_exists(**opts_dict)

            exists_data.append(opts_dict)

        return nested_group(exists_data, col_label)