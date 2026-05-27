'''
HW: Organise files in folder into database
'''
import os
import pandas as pd
from typing import List, Optional, Pattern, Tuple, Dict, Any
import re
from pathlib import Path

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

        # Atomic reassignment so the background scan thread never sees an in-place mutation
        self._dataframe = self._dataframe.sort_values(merge_on+list(kwargs.keys()), ascending=False)

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
        self._name = name
        self._directory = Path(directory)
        self._subdir = Path(subdir)
        self._regex = regex
        self._additional_elements = additional_elements
        self._last_dir_mtime: float = 0.0
        self._last_file_mtime: float = 0.0

        self._search_terms = ['run', 'trigger']
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

        max_mtime: float = 0.0
        for entry in os.scandir(search_path):
            try:
                entry_mtime = entry.stat(follow_symlinks=False).st_mtime
            except OSError:
                continue
            if entry_mtime > max_mtime:
                max_mtime = entry_mtime
            self.__build_search_dict(search_dict, Path(entry.path), regex_search_str)

        self._last_file_mtime = max_mtime
        self._last_dir_mtime = search_path.stat().st_mtime

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

    def refresh(self) -> bool:
        '''Incrementally scan for files added since the last scan. Returns True if new rows were added.'''
        search_path = self._directory / self._subdir
        try:
            dir_mtime = search_path.stat().st_mtime
        except OSError:
            return False

        if dir_mtime == self._last_dir_mtime:
            return False  # directory unchanged — skip scan entirely

        all_cols = ['run', 'trigger'] + (self._additional_elements or [])
        regex_search_str = re.compile(self._regex, re.X)
        new_entries: Dict[str, list] = {n: [] for n in all_cols}
        new_entries[self._name] = []
        max_mtime = self._last_file_mtime

        for entry in os.scandir(search_path):
            try:
                entry_mtime = entry.stat(follow_symlinks=False).st_mtime
            except OSError:
                continue
            if entry_mtime > max_mtime:
                max_mtime = entry_mtime
            if entry_mtime <= self._last_file_mtime:
                continue  # already known
            match = regex_search_str.match(entry.name)
            if not match:
                continue
            try:
                row_vals = [int(match[s]) for s in all_cols]
            except Exception:
                continue
            for s, v in zip(all_cols, row_vals):
                new_entries[s].append(v)
            new_entries[self._name].append(Path(entry.path))

        self._last_dir_mtime = dir_mtime
        self._last_file_mtime = max_mtime

        if not new_entries[self._name]:
            return False

        new_df = pd.DataFrame.from_dict(new_entries)
        combined = pd.concat([self._dataframe, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=[self._name], keep='last')
        self._dataframe = combined.sort_values(list(combined.columns), ascending=False)
        return True

class DQMImageDatabaseCollection :
    '''
    Handler to handle all the BASE databases for a DQMDisplay
    '''
    def __init__(self):
        self._displays: Dict[str, DQMImageDatabase] = {}
        self._views = {}

        self._unique_combo_db = None
        self._new_df_added = True

        self._combined_df: Optional[pd.DataFrame] = None
        self._existing_combos: Optional[pd.DataFrame] = None


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

    def get_all_views(self):
        return self._views

    @classmethod
    def get_extra_col_unq(cls, dataframe: DQMImageDatabase, extra_col: Optional[str]=None):
        '''Gets unique values for some extra column
        '''
        if extra_col is None:
            return None

        # We then sort it for ease of lookup
        return dataframe.get_unique(extra_col).copy()


    def add_display(self, new_dataframe: DQMImageDatabase):
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
        
        if unq_page_col_indices is not None:
            unq_page_col_indices = unq_page_col_indices.tolist()

        self._views[view_name] = {
            'display_name': dataframe_name,
            'page_col_name': extra_col,
            'page_col_indices': unq_page_col_indices
        }
        

    def check_exists(self, **kwargs):
        """
        Much faster existence check using cached dataframe.
        """
        existing = self.get_existing_combos()
        if existing.empty:
            return []

        # filter down to matching rows
        mask = pd.Series(True, index=existing.index)
        for col, val in kwargs.items():
            if col in existing.columns:
                mask &= existing[col] == val
        filtered = existing[mask]

        return_list = []
        for view_name, opts in self._views.items():
            
            
            view_rows = filtered[filtered["view_name"] == view_name]
            base_dict = {"name": view_name, **kwargs}

            if opts["page_col_name"] is None:
                return_list.append({**base_dict, "exists": not view_rows.empty})
            else:
                col = opts["page_col_name"]
                for val in opts["page_col_indices"]:
                    exists = not view_rows[view_rows[col] == val].empty
                    return_list.append({**base_dict, col: val, "exists": exists})

        return return_list


    def refresh_all(self):
        '''Check all display directories for new files and invalidate caches if anything changed.'''
        # Evaluate ALL databases — don't short-circuit with any() on a generator
        results = [db.refresh() for db in self._displays.values()]
        if any(results):
            self._unique_combo_db = None
            self._combined_df = None
            self._existing_combos = None
            self._new_df_added = True

    def get_unique_cols_all_db(self, col_labs: List[str]):
        # More efficient to cache this infomration
        if not self._new_df_added and self._unique_combo_db is not None:
            return self._unique_combo_db

        # First time/if a new object has been added
        concat_obj = pd.concat((d.as_dataframe()[col_labs].drop_duplicates() for d in self._displays.values()), ignore_index=True)
        self._unique_combo_db = concat_obj.drop_duplicates()
        # Have to make implicit copy to stop pandas complaining here
        self._unique_combo_db = self._unique_combo_db.sort_values(col_labs, ascending=False)
        self._unique_combo_db.reset_index(drop=True, inplace=True)

        # Means we don't need to regenerate everything from scratch
        self._new_df_added = False

        return self._unique_combo_db
    
    def get_combined_dataframe(self) -> pd.DataFrame:
        """
        Combine all displays into one dataframe with view metadata.
        Columns: run, trigger, view_name, and optional extra cols.
        """
        if self._combined_df is not None and not self._new_df_added:            
            return self._combined_df

        dfs = []
        for view_name, opts in self._views.items():
            df = self._displays[opts['display_name']].as_dataframe().copy()
            df["view_name"] = view_name

            # ensure the extra col exists if defined
            if opts["page_col_name"] is not None and opts["page_col_name"] not in df.columns:
                raise KeyError(f"{opts['page_col_name']} not in dataframe {opts['display_name']}")

            dfs.append(df)

        if not dfs:
            self._combined_df = pd.DataFrame()
        else:
            self._combined_df = pd.concat(dfs, ignore_index=True)

        self._combined_df = self._combined_df.loc[:,~self._combined_df.columns.duplicated()].copy()

        self._new_df_added = False
        self._existing_combos = None  # invalidate dependent cache
    
        return self._combined_df
    
    

    def get_existing_combos(self) -> pd.DataFrame:
        """
        Precompute all (run, trigger, view_name, [extra cols]) that actually exist.
        """
        if self._existing_combos is not None and not self._new_df_added:
            return self._existing_combos

        combined = self.get_combined_dataframe()
        if combined.empty:
            self._existing_combos = pd.DataFrame()
            return self._existing_combos

        keep_cols = ["run", "trigger", "view_name"]

        for opts in self._views.values():
            if opts["page_col_name"] is not None and opts["page_col_name"] not in keep_cols:
                keep_cols.append(opts["page_col_name"])

        self._existing_combos = combined[keep_cols].drop_duplicates()
        return self._existing_combos

