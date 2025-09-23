import numpy as np
import pandas as pd

import pytest

from dqmdisplay.file_operations.file_database import NaviagableDataframe, DQMImageDatabase, ImageExistsDatabase

# make runs
N_ENTRIES = 10
N_GROUPS = 5

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



@pytest.fixture(scope="session")
def dummy_file_maker(tmp_path_factory):
    a = tmp_path_factory.mktemp("test_files_a")
    b = tmp_path_factory.mktemp("test_files_b")
    # We'll make some dummy event displays
    a_runs = [1, 2, 3]
    b_runs = [1, 4, 5]
    a_triggers = [1, 2, 3]
    b_triggers = [3, 4, 5]

    for ar, br in zip(a_runs, b_runs):
        for at, bt in zip(a_triggers, b_triggers):
            (a / f"A_run{ar}_trigger{at}.png").touch()
            (b / f"B_run{br}_trigger{bt}.png").touch()

    return a, b

def test_image_database(dummy_file_maker):
    # Make some test files
    file_dir, _ = dummy_file_maker

    database = DQMImageDatabase(file_dir.parent, file_dir.name,
                                "my_database",
                                r"A_run(?P<run>\d+)_trigger(?P<trigger>\d+).png"
                                )
    # Check naming
    assert database.name == "my_database"
    
    # Check the file names are correct
    assert database.dataframe.get_eq(**{'run': 1, 'trigger': 1})[database.name].to_list()[0].name == 'A_run1_trigger1.png'
    
def test_image_exists_database(dummy_file_maker):
    file_a, file_b = dummy_file_maker
    
    database_a = DQMImageDatabase(file_a.parent, file_a.name,
                            "my_database_a",
                            r"A_run(?P<run>\d+)_trigger(?P<trigger>\d+).png"
                            )


    database_b = DQMImageDatabase(file_b.parent, file_b.name,
                            "my_database_b",
                            r"B_run(?P<run>\d+)_trigger(?P<trigger>\d+).png"
                            )
    
    image_exists_db = ImageExistsDatabase([database_a, database_b])
    
    check_db = image_exists_db.check_has_col(**{'run': 1, 'trigger': 2})    
    assert check_db['my_database_a']
    assert not check_db['my_database_b']