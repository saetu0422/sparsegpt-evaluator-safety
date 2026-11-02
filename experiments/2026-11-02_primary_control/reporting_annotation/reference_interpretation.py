"""Post-analysis reporting annotation only. Does not recompute estimates/tests."""
import math

def interval_relation(interval, reference=.10):
    if interval is None:return 'unavailable'
    low,high=interval
    if not all(math.isfinite(x) for x in (low,high,reference)) or low>high:raise ValueError('Invalid interval/reference')
    if high<reference:return 'wholly_below_reference'
    if low>reference:return 'wholly_above_reference'
    return 'contains_or_touches_reference'
