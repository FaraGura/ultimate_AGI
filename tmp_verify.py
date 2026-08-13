import importlib.util
spec = importlib.util.spec_from_file_location('test_overnight_learning', 'tests/test_overnight_learning.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.test_format_log_block_keeps_full_content()
print('verification passed')
