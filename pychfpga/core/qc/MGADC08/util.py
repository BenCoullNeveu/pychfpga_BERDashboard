import collections
import sys
import os
import yaml
import re
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


class NameSpace(collections.OrderedDict):

    # def __init__(self, *args, **kwargs):

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except KeyError:  # Re-raise, but preserve traceback info
            raise AttributeError, sys.exc_info()[1], sys.exc_info()[2]
    def __setattr__(self, name, value):
        if name.startswith('_' + collections.OrderedDict.__name__ + '__'):  # don't put special names in the dict. Needed for Ordereddict to initialize properly.
            super(NameSpace, self).__setattr__(name, value)
        else:
            self.__setitem__(name, value)
    def __setitem__(self, key, value):
        _setitem = super(NameSpace, self).__setitem__
        if isinstance(value, collections.Mapping) and not isinstance(value, NameSpace):
            _setitem(key, NameSpace(value))
        else:
            _setitem(key, value)
    def __dir__(self):
        return list(
            set(self.__dict__.keys()) |
            set.union(*[set(dir(cls)) for cls in type(self).mro()]) |
            set(self.keys()))
    def as_dict(self):
            def todict(v):
                if isinstance(v, collections.Mapping):
                    return {k: todict(i) for k, i in v.items()}
                elif isinstance(v, collections.Sequence):
                    return [todict(i) for i in v]
                else:
                    return v
            return todict(self)
    def as_yaml(self):
        return yaml.dump(self.as_dict(), default_flow_style=False)


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
    for item in menu:
        if 'description' in item:
            if 'key' in item:
                print "%02s. %s" % (item['key'], item['description'])
            else:
                print "    %s" % item['description']

    while True:
        choice = raw_input("Enter choice%s: " % (' [%s]' % default if default else '')).strip()
        pattern_match = parse_pattern(choice or default, menu)
        if pattern_match:
            return pattern_match
        print "Choice is not valid. Valid choices are %s. Please try again." % (', '.join(item['key'] for item in menu if item.get('key',None)))

def parse_pattern(text, pattern_list):
    """ Parse a string and return a dictionary containing the parsed contents.
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

