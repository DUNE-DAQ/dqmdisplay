'''
HW: Organise files in folder into database
'''
import pandas as pd
from typing import List, Optional, Callable, Tuple, Dict, Any
import re
from pathlib import Path


def check_cols_in_db(database: pd.DataFrame, col_list: List[str]):
    ''' Helper function for kwargs checking
    '''
    if set(col_list).difference(c:=database.columns):
        raise ValueError(f"Provided {col_list} but columns are {c}")


class NaviagableDataframe:
    '''
    Wrapper object to simplify dataframe queries allowing for more natural next/prev operations
    '''
    def __init__(self, dataframe: pd.DataFrame):
        dataframe.sort_values(list(dataframe.columns), ascending=True, inplace=True)
        self._dataframe = dataframe
    
    
    def as_dataframe(self)->pd.DataFrame:
        '''Returns the raw pandas dataframe'''
        return self._dataframe
    

    def query_db_cond(self, condition: Callable[..., pd.DataFrame], **kwargs)->pd.DataFrame:
        '''Safe wrapper to ensure we check dataframe nicely'''
        check_cols_in_db(self._dataframe, list(kwargs.keys()))
        return self._dataframe[condition(kwargs)]
    
    def get_eq(self, **kwargs)->'pd.DataFrame':
        '''Check if values in dict are equal to kwargs'''
        mask = pd.Series(True, index=self._dataframe.index)        
        
        for col, val in kwargs.items():
            mask &= self._dataframe[col] == int(val)  # "prev" means greater than for sorted ascending
        
        return self._dataframe[mask]
     
    def get_next(self, **kwargs)->Tuple[pd.DataFrame, Dict[str, int]] | Tuple[None, dict]:
        '''
        Get the prev row(s) from the one satisfying **kwargs
        '''
        cond = lambda k, v: self._dataframe[k] > v
        return self._get_adjacent(cond, True, **kwargs)

    def get_prev(self, **kwargs)->Tuple[pd.DataFrame, Dict[str, int]] | Tuple[None, dict]:
        '''
        Get the next row(s) from the one satisfying **kwargs
        '''
        cond = lambda k, v: self._dataframe[k] < v
        return self._get_adjacent(cond, False, **kwargs)

    
    def _get_adjacent(self, condition: Callable[[str, int], pd.Series], ascending: bool, **kwargs):
        mask = pd.Series(True, index=self._dataframe.index)
        # We go back through the mask
        mask_dict = {k: self._dataframe[k]==int(v) for k, v in kwargs.items()}
        # Go backwards through dict
        for k in reversed(mask_dict.keys()):
            mask_dict[k] = condition(k, int(kwargs[k]))
            m_copy = mask.copy()
            for m in mask_dict.values():
                m_copy &= m

            if not self._dataframe[m_copy].empty:
                mask = m_copy
                break

        adj = self._dataframe[mask]
        kwarg_list = list(kwargs.keys())
        
        sort_adj = adj.sort_values(kwarg_list, inplace=False, ascending=ascending)

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


class DQMImageDatabase:
    '''
    Stores DQM images for event displays
    '''
    
    def __init__(self, directory: str | Path, subdir: str | Path, name: str, regex: str, additional_elements: Optional[List[str]]=None):
        '''
        Build the database
        '''
        self._search_terms = ['run', 'trigger']

        regex_search_str = re.compile(regex, re.X)
        self._name = name

        if additional_elements is not None:
            self._search_terms.extend(additional_elements)

        search_path = Path(directory) / Path(subdir)
        
        if not search_path.exists():
            raise FileNotFoundError(f"Couldn't find directory {search_path}")
        
        # Now we fill our dataframe [start as dictionary for speed]                
        search_dict = {n : [] for n in self._search_terms}
        search_dict[name] = []

        # Check for matches with regex
        for f in search_path.iterdir():
            match = regex_search_str.match(f.name)
            
            # No match!
            if not match:
                continue
            
            # Add to file
            
            for s in self._search_terms:
                try:
                    search_dict[s].append(int(match[s]))
                except Exception as e:
                    raise ValueError(f"Couldn't find {s} when matching {match} to {f.name}") from e                
                
            # Append the FULL file name
            search_dict[name].append(f)
        
        self._full_db = NaviagableDataframe(pd.DataFrame.from_dict(search_dict))
    
    @property
    def name(self):
        return self._name
    
    @property
    def dataframe(self):
        return self._full_db    

class ImageExistsDatabase:
    '''
    Essentially a record of unique values for some given properties in a dataframe
    '''
    def __init__(self, databases: List[DQMImageDatabase], merge_on: List[str] = ['run', 'trigger']):
        # Check they all have the 'merge on' columns
        for d in databases:
            check_cols_in_db(d.dataframe.as_dataframe(), merge_on)
        
        # Full database to query
        self._databases = databases
        
        self._lookup = {d.name: d for d in self._databases}

        # We can also merge on columns
        merge_list = []
        for db in self._databases:
            # Make unique copy
            col_db = db.dataframe.as_dataframe()[merge_on].drop_duplicates().copy()
            col_db[db.name] = True
            merge_list.append(col_db)
        
        # Merge together
        merged_df = merge_list[0]
        for d in merge_list[1:]:
            merged_df = merged_df.merge(d, on=merge_on, how='outer')
            
        # Now we fill the NAs with false
        merged_df[self.database_names] = merged_df[self.database_names].astype(bool).fillna(False)
        self._merged_df = NaviagableDataframe(merged_df)
        
    def get_database(self, database_name: str):
        return self._lookup.get(database_name, None)

        
    @property
    def database_names(self):
        return [d.name for d in self._databases]

    def as_navigable(self):
        return self._merged_df

    def check_has_col(self, **kwargs):
        # Get the cols where condition is satisfied
        cols = self._merged_df.get_eq(**kwargs)
        
        return_dict = {}
        
        for d in self._databases:
            if all(cols[d.name]):
                return_dict[d.name] = d.dataframe.get_eq(**kwargs)
            else:
                return_dict[d.name] = None                
        
        return return_dict