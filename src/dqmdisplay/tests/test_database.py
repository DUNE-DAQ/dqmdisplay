import numpy as np
import pandas as pd


from dqmdisplay.file_operations.file_database import NaviagableDataframe, DQMImageDatabase, ImageExistsDatabase

# make runs
N_ENTRIES = 100
N_GROUPS = 20

# We'll add in runs/triggers
runs = np.repeat(np.arange(1, N_ENTRIES+1), N_GROUPS)
runs = np.sort(runs)
triggers = np.tile(np.arange(1, N_GROUPS+1), N_ENTRIES)

# Make some arbitrary file names
files = [f"file_name_{i}" for i in range(N_ENTRIES*N_GROUPS)]

TEST_DATA = pd.DataFrame({'run': runs, 'trigger': triggers, 'files': files})


def test_navigable_dataframe_basic():
    '''
    Test if the navigation features are set up correctly 
    '''
    
    navigable = NaviagableDataframe(TEST_DATA)
    
    assert not navigable.as_dataframe().empty, "No data frame has been set!"
    
    # Should be the bottom of the original dataframe
    assert navigable.as_dataframe().iloc[0].to_list() == [N_ENTRIES, N_GROUPS, f"file_name_{N_ENTRIES*N_GROUPS-1}"]
    
    # Now we test the equality conditions
    search_cond = {'run': 1, 'trigger': 1}
    file_searched = navigable.get_eq(**search_cond)['files'].to_list()
    assert len(file_searched) == 1
    assert file_searched[0] == "file_name_0"
    
    # Okay now we know the single search works, we'll get ALL files for a given run
    test_file_list = [f"file_name_{i}" for i in range(N_GROUPS-1, -1, -1)]
    search_cond = {'run': 1}
    file_searched = navigable.get_eq(**search_cond)['files'].to_list()
        
    # Same length
    assert len(file_searched) == len(test_file_list), "Different number of files found"
    # Same entries
    assert not set(file_searched).difference(test_file_list), "Different files found"
    # Same order
    assert file_searched == test_file_list, "File order is different"
    
    _, latest = navigable.get_latest()
    assert latest == {'run': N_ENTRIES, 'trigger': N_GROUPS}
    
def test_navigable_dataframe_next_prev():
    '''
    Test if the dataframe is correctly set up to go backwards/forwards
    '''
    navigable = NaviagableDataframe(TEST_DATA)

    # Now we test navigation
    current_file_vals = {'run': 2, 'trigger': 2}
    _, trigger_vals = navigable.get_prev(**current_file_vals)
    assert trigger_vals == {'run': 2, 'trigger': 1}
    # Go back one more
    _, trigger_vals_back = navigable.get_prev(**trigger_vals)
    assert trigger_vals_back == {'run': 1, 'trigger': N_GROUPS}
    
    # Now we check what happens on the first row
    assert navigable.get_prev(**{'run': 1, 'trigger': 1}) == (None, {})
    
    # Now we go the other way!
    _, next_vals = navigable.get_next(**trigger_vals_back)
    assert next_vals == trigger_vals
    _, origin_vals = navigable.get_next(**next_vals)
    assert origin_vals == current_file_vals
    
    # Finally we want to make sure it doesn't go outside the df
    assert navigable.get_next(**{'run': N_ENTRIES, 'trigger': N_GROUPS}) == (None, {})

