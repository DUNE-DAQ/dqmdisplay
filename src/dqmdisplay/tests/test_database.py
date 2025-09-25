import numpy as np
import pandas as pd
import itertools


import pytest

from dqmdisplay.file_operations.file_database import NavigableDataframe, DQMImageDatabase, DQMImageDatabaseCollection

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

A_RUNS = [1, 2, 3]
A_ELEMENTS = [1,2,3]
A_TRIGGERS = [1, 2, 3]
a_combos = list(itertools.product(A_RUNS, A_TRIGGERS))
# uniuqe combos
A_RUN_TRIGGERS = pd.DataFrame(a_combos, columns=['run', 'trigger'])
A_REGEX=r"A_run(?P<run>\d+)_trigger(?P<trigger>\d+)_element_id(?P<element_id>\d+).png"

B_RUNS = [1, 4, 5]
B_TRIGGERS = [3, 4, 5]
b_combos = list(itertools.product(B_RUNS, B_TRIGGERS))
B_RUN_TRIGGERS = pd.DataFrame(b_combos, columns=['run', 'trigger'])

B_REGEX=r"B_run(?P<run>\d+)_trigger(?P<trigger>\d+).png"

def test_navigable_dataframe_basic():
    '''
    Test if the navigation features are set up correctly 
    '''
    
    navigable = NavigableDataframe(TEST_DATA)
    
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
    navigable = NavigableDataframe(TEST_DATA)

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
    
    

    for ar, br in zip(A_RUNS, B_RUNS):
        for at, bt in zip(A_TRIGGERS, B_TRIGGERS):
            (b / f"B_run{br}_trigger{bt}.png").touch()
            for ae in A_ELEMENTS:
                (a / f"A_run{ar}_trigger{at}_element_id{ae}.png").touch()

    return a, b

def test_image_database(dummy_file_maker):
    # Make some test files
    file_dir, _ = dummy_file_maker

    database = DQMImageDatabase(file_dir.parent, file_dir.name,
                                "my_database",
                                A_REGEX,
                                additional_elements=['element_id']
                                )
    # Check naming
    assert database.name == "my_database"
    # Check the file names are correct
    searched =  database.get_eq(**{'run': 1, 'trigger': 1})
    searched = searched.sort_values('element_id')

    comp_list = [s.name for s in searched['my_database'].to_list()]    
    assert comp_list == [f'A_run1_trigger1_element_id{i}.png' for i in A_ELEMENTS]

    # Now we wanna see if we can also get the element ids correct!
    searched =  database.get_next(**{'run': 1, 'trigger': 1})
    
def test_image_database_collection(dummy_file_maker):
    '''Tests for multi-image db'''
    file_a, file_b = dummy_file_maker
    
    database_a = DQMImageDatabase(file_a.parent, file_a.name,
                            "my_database_a",
                            A_REGEX,
                            additional_elements=['element_id']
                            )


    database_b = DQMImageDatabase(file_b.parent, file_b.name,
                            "my_database_b",
                            B_REGEX,
                            )
    
    image_collection = DQMImageDatabaseCollection()
    image_collection.add_display(database_a)
    image_collection.add_display(database_b)
    
    image_collection.add_view("my_database_a", "my_database_a")
    image_collection.add_view("my_database_b", "my_database_b")
    image_collection.add_view("my_database_a_element", "my_database_a", "element_id")
    
    test_disp = { 
                    'my_database_a': 
                    {
                        'display_name': "my_database_a",
                        'page_col_name': None,
                        'page_col_indices': None
                    },
                    'my_database_b': 
                    {
                        'display_name': "my_database_b",
                        'page_col_name': None,
                        'page_col_indices': None
                    },
                    'my_database_a_element': 
                    {
                        'display_name': "my_database_a",
                        'page_col_name': 'element_id',
                        'page_col_indices': A_ELEMENTS
                    },
                }
    
    for name, opts in test_disp.items():
        d = image_collection._views.get(name, None)
        # Check this is there
        assert d is not None
        
        for opt_d, opt_test in zip(d.values(), opts.values()):
            if isinstance(opt_d, list) or isinstance(opt_test, list):
                assert not set(opt_d).difference(opt_test)
            else:
                assert opt_d == opt_test
    
    # Now we want to see if it exists
    exist_check = image_collection.check_exists(**{'run': 2, 'trigger': 1})    
    
    expected_exist = [{'name': 'my_database_a',
                            'run': 2,
                            'trigger': 1,
                            'exists': True},
                           
                           {'name': 'my_database_b',
                            'run': 2,
                            'trigger': 1,
                            'exists': False
                            },

                            {'name': 'my_database_a_element',
                            'run': 2,
                            'trigger': 1,
                            'element_id': 1,
                            'exists': True
                            },

                            {'name': 'my_database_a_element',
                            'run': 2,
                            'trigger': 1,
                            'element_id': 2,
                            'exists': True
                            },
                            
                            {'name': 'my_database_a_element',
                            'run': 2,
                            'trigger': 1,
                            'element_id': 3,
                            'exists': True
                            },
                    ]
    
    assert sorted(exist_check, key=lambda x: sorted(x.items())) == sorted(expected_exist, key=lambda x: sorted(x.items()))
        
    # Check the run/trigger getting process is the same
    a_b_unique_triggers = pd.concat((A_RUN_TRIGGERS, B_RUN_TRIGGERS), ignore_index=True)
    a_b_unique_triggers = a_b_unique_triggers.drop_duplicates()
    a_b_unique_triggers.sort_values(['run', 'trigger'], ascending=False, inplace=True)
    a_b_unique_triggers.reset_index(drop=True, inplace=True)
        
    pd.testing.assert_frame_equal(a_b_unique_triggers, image_collection.get_unique_cols_all_db(['run', 'trigger']))
    
    