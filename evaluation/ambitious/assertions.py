def matches(actual,expected):
    """Documented result fields must match; implementation-specific extras allowed."""
    if isinstance(expected,dict):return isinstance(actual,dict)and all(k in actual and matches(actual[k],v)for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list)and len(actual)==len(expected)and all(matches(a,b)for a,b in zip(actual,expected))
    return actual==expected
