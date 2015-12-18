
import sys
import os
import re
import datetime
#  ... more imports below

def add_paths(*paths):
    """ Add folders to the current search path.

    This is needed to access packages that are in folders above the one from which we run scripts.
    This function makes sure that the paths are not duplicated.
    """
    for path in paths:
        fullpath = os.path.realpath(path)
        if fullpath not in sys.path:
            sys.path.insert(1, fullpath)

add_paths('..')  # needed to find labpy
add_paths('../..')  # needed to find icecore

import labpy  # McGill's GPIB & LAN instrument library
import icecore
from icecore import NameSpace, XReport

def run_tests(config_file):
    cfg = load_config(config_file)

    test_results_folder = cfg.test_results_folder
    mgadc08_model_number = cfg.mgadc08_model_number

    # instr = open_instruments(cfg.instruments, ['dmm'])
    # instr.dmm.display('Hello', 'SCAN serial number')
    current_serial = cfg.debug.default_serial
    current_model = cfg.debug.default_model
    test_list = NameSpace(cfg.test_list)  # convert list of (key,values) into an OrderedDict


    # load test menu and convert each dict element to NameSpace to simplify code
    test_menu = [NameSpace(menu_item) for menu_item in cfg.menu]


    # Update menu with information from the test list
    for menu_item in test_menu:
        if menu_item.type == 'test':
            test = test_list[menu_item.test_tag]
            if not menu_item.get('description', None):  # Take description from the tets list if there is none
                menu_item.description = test.description
            menu_item.regex = '(%s|%s)' % (test.path, menu_item.test_tag) # have the menu recognize the test path or key as an other way to select the test

    while True:
        print
        print
        print '---------------------------------------------'
        if current_model and current_serial:
            print 'Currently testing  %s SN%s' % (current_model, current_serial)
        else:
            print ' !!! NO SERIAL NUMBER CURRENTLY SELECTED !!!'
        print '---------------------------------------------'
        print
        # Get a summary of all tests run so far
        test_folder = os.path.join(test_results_folder, '%s_SN%s' % (current_model, current_serial))
        summary = XReport.generate_test_summary(input_folder=test_folder, required_tests=cfg.test_list)

        # Update the menu to indicate which tests have passed.
        # Also use that information to determine the next test to run by default.
        default_choice = None
        for menu_item in test_menu:
            if menu_item.type == 'test':
                test_tag = menu_item.test_tag
                passed_list = summary.get_passed(test_list[test_tag].path)
                dependents_ok = check_test_dependencies(test_tag, test_list, summary)
                if not passed_list:
                    menu_item.status = ' ?  '
                    if not default_choice and dependents_ok:
                        default_choice = menu_item.key
                elif all(passed_list):
                    menu_item.status = 'PASS'
                else:
                    menu_item.status = 'FAIL'
                    if not default_choice and dependents_ok:
                        default_choice = menu_item.key
                menu_item.status += ', Ready' if dependents_ok and current_model and current_serial else ''
        if not default_choice or not current_model or not current_serial:
            default_choice = 'Q'

        selection = select_menu_item(test_menu, default=default_choice)

        if selection.type == 'exit':
            # instr.dmm.display('Bye!', '')
            break
        elif selection.type == 'board_info':
            if selection.model not in mgadc08_model_number:
                print
                print '!!!! This is not a valid serial number for this test. Try again.'
            else:
                current_model = selection.model
                current_serial = selection.serial
                default_choice = selection.next_key
                # instr.dmm.display(current_model, current_serial)
        elif selection.type == 'test':
            if not current_serial or not current_model:
                print 'Please enter or scan a serial number before beginning a test'
                continue
            # summary_data = xr.generate_summary(summary_filename, data_folder)
            test = test_list[selection.test_tag]
            nose_test_path = test.path
            test_date = datetime.datetime.now().isoformat().replace(':','_')+'_' if not cfg.debug.no_date else ''
            test_file_name = '%s%s.pdf' %  (test_date, nose_test_path.replace(':', '.'))
            summary_file_name = '%s/%s_SN%s.pdf' %  (test_results_folder, current_model, current_serial)

            if not os.path.exists(test_folder):
                os.makedirs(test_folder)

            full_test_filename = os.path.join(test_folder, test_file_name)
            print
            print 'Running test %s' % nose_test_path
            print 'Test data will be stored in %s' % full_test_filename
            print
            r = XReport.run(nose_test_path, xfile=full_test_filename, xformat=cfg.xformat, config_file=config_file, model=current_model, serial=current_serial)
            # if r.passed:
            #     default_choice = selection.next_key
            # else:
            #     default_choice = 'Q'
            t = XReport.generate_test_summary(input_folder=test_folder, required_tests=cfg.test_list, output_filename=summary_file_name, title='%s_SN%s Summary Test Report' % (current_model, current_serial))
    return locals()


def check_test_dependencies(test_tag, test_list, test_summary):
    test = test_list[test_tag]
    dependencies = test.get('dependencies', []) or []   # return an empty list if the dependency is not there or is None
    if not isinstance(dependencies, list):
        dependencies = [dependencies]
    passed = True
    for dep_tag in dependencies:
        passed_list = test_summary.get_passed(test_list[dep_tag].path)
        passed = passed and bool(passed_list) and all(passed_list) and check_test_dependencies(dep_tag, test_list, test_summary)
    return passed


def select_menu_item(menu, default=''):
    """
    Prints a menu and ask the user to select an item.

    ``menu`` is a list of items. Each item is a list of [key, description, user_args], where the first element
    is the key and the second is the description.

    If ``pattern_list`` is specified, and if the used input matches the
    specified pattern, the function returns [None, None, parsed_pattern_dict],
    where parsed_pattern_dict is a dict containing the parsed pattern is
    returned instead.

    Returns the list corresponding to the selected item.
    """
    print 'Select the operation to execute.\n'

    key_width = 0
    status_width = 0
    for menu_item in menu:
        key_width = max(key_width, len(menu_item.get('key', '')))
        status_width = max(status_width, len(menu_item.get('status', '')))
    fmt = ('%%-%is  ' % status_width)  + ('%%-%is. ' % key_width) + '%s'
    for item in menu:
        if 'description' in item:
            # if 'key' in item:
                print fmt % (item.get('status',''), item.get('key',''), item.get('description',''))
            # else:
            #     print "    %s" % item['description']

    while True:
        choice = raw_input("Enter choice%s: " % (' [%s]' % default if default else '')).strip()
        pattern_match = find_menu_item(choice or default, menu)
        if pattern_match:
            return pattern_match
        print "Choice is not valid. Valid choices are %s. Please try again." % (', '.join(item['key'] for item in menu if item.get('key', None)))

def find_menu_item(text, pattern_list):
    """ Finds the menu item whose 'key' or 'regex' pattern matches the specified text.
    Returns None if no pattern matched.
    """

    def string(matches, value):
        return value

    def regex_group(matches, index):
        return matches.group(index)

    for pattern in pattern_list:
        # print pattern
        pattern = pattern.copy()
        if 'regex' in pattern:
            matches = re.match(pattern['regex'] + '$', text, re.I)
            if matches:
                args = {}
                for key, value in pattern.items():
                    if isinstance(value, str) and key not in ('key', 'regex'):  # regex has curly braces...
                        # print matches.groups(), value, key
                        # sanitized_value = value.replace('{','{{').replace('}','}}')
                        args[key] = value.format(*matches.groups())
                    else:
                        args[key] = value
                    # elif isinstance(value, int):
                    #     args[key] = group(matches, value)
                    # elif isinstance(value, dict):
                    #     method = locals()[value.pop('method')]
                    #     args[key] = method(matches=matches, **value)
                    # elif isinstance(value, list):
                    #     method = locals()[value[0]]
                    #     args[key] = method(matches, *value[1:])
                return NameSpace(args)
        if 'key' in pattern:
            if text.lower() == pattern['key'].lower():
                return NameSpace(pattern)
    return None


def load_config(filename):
        print 'Loading config file %s' % filename
        with open(filename, 'rb') as yamlfile:
            cfg = NameSpace(icecore.load_yaml(yamlfile))
        return cfg

def open_instruments(instruments, filter_list=None):
    """ Create and open objects representing instruments.

    ``instruments`` is a dict containing the list of instruments. Each entry is in the form:
        instrument_name : {labpy_object: my_labpy_object, ...}

    where labpy_object is the mandatory field that describes the name of the
    labpy class used to create the instrument. All other keywoards areguments
    are passed to that class' constructor to create the object.

    Returns a dict-like NameSpace of instrument objects with keys identical to those provided in the instrument list.
    """
    # opening communication with instruments
    if filter_list:
        instruments = NameSpace((key, instruments[key]) for key in filter_list)

    instr = NameSpace()

    for instr_name, connection_parameters in instruments.items():
        # print instr_name, connection_parameters
        labpy_object_name = connection_parameters.pop('labpy_object')
        labpy_object = getattr(labpy, labpy_object_name)
        # print labpy_object
        instr[instr_name] = labpy_object(**connection_parameters)
    return instr

