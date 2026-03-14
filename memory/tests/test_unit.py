from memory.main import get_params_hash

def test_get_params_hash_stability():
    params1 = {"a": 1, "b": 2}
    params2 = {"b": 2, "a": 1}
    assert get_params_hash(params1) == get_params_hash(params2)

def test_get_params_hash_difference():
    params1 = {"a": 1, "b": 2}
    params2 = {"a": 1, "b": 3}
    assert get_params_hash(params1) != get_params_hash(params2)
