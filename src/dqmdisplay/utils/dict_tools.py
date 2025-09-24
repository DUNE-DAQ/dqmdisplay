from collections import defaultdict

def nested_group(dicts, keys):
    if not keys:  # no more grouping keys, return the list of dicts
        return dicts
    
    key = keys[0]
    grouped = defaultdict(list)
    for d in dicts:
        grouped[d[key]].append(d)
    
    # recurse for remaining keys
    return {
        k: nested_group(v, keys[1:])
        for k, v in grouped.items()
    }
