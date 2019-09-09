if __name__ == '__main__':
	""" Run the test in this file."""
	import util
	v = util.run_tests('qcengine_test_config.yaml')
	locals().update(v) # bring local variables from the test runner into the current namespace for easier debugging
