def test_import_main():
    import importlib
    mod = importlib.import_module('main')
    assert mod is not None
