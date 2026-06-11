from lib.xvg_parser import running_average


def test_running_average_window_1_is_identity():
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert running_average(data, 1) == data


def test_running_average_window_3_center():
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = running_average(data, 3)
    assert abs(result[2] - 3.0) < 1e-9


def test_running_average_edge_clips_to_available():
    data = [10.0, 20.0, 30.0]
    result = running_average(data, 5)
    expected = (10.0 + 20.0 + 30.0) / 3
    assert abs(result[0] - expected) < 1e-9


def test_running_average_empty_returns_empty():
    assert running_average([], 3) == []


def test_running_average_window_larger_than_data():
    data = [2.0, 4.0]
    result = running_average(data, 100)
    expected = (2.0 + 4.0) / 2
    assert all(abs(v - expected) < 1e-9 for v in result)
