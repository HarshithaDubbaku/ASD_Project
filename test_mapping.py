import pytest

# Re-implement the small aggregation logic from app.py so tests are independent
def aggregate_feature(vals, mode='majority', weighted_threshold=0.5):
    if mode == 'any':
        return 1 if any(vals) else 0
    if mode == 'majority':
        if not vals:
            return 0
        return 1 if sum(vals) > (len(vals) / 2.0) else 0
    if mode == 'weighted':
        # vals expected as list of (value, weight)
        total = 0.0
        weight_sum = 0.0
        for v, w in vals:
            total += v * w
            weight_sum += w
        if weight_sum <= 0:
            return 0
        return 1 if (total / weight_sum) >= weighted_threshold else 0
    return 1 if any(vals) else 0


def test_any_mode():
    # single Yes should trigger
    vals = [1, 0, 0, 0]
    assert aggregate_feature(vals, mode='any') == 1
    # all No should not
    assert aggregate_feature([0, 0, 0], mode='any') == 0


def test_majority_mode_strict():
    # For n=4, strict majority requires >2
    assert aggregate_feature([1, 0, 0, 0], mode='majority') == 0
    assert aggregate_feature([1, 1, 0, 0], mode='majority') == 0
    assert aggregate_feature([1, 1, 1, 0], mode='majority') == 1
    # single element
    assert aggregate_feature([1], mode='majority') == 1
    assert aggregate_feature([0], mode='majority') == 0


def test_weighted_mode():
    # two items with weights
    vals = [(1, 0.6), (0, 0.4)]
    assert aggregate_feature(vals, mode='weighted', weighted_threshold=0.5) == 1
    vals = [(1, 0.4), (0, 0.6)]
    assert aggregate_feature(vals, mode='weighted', weighted_threshold=0.5) == 0
