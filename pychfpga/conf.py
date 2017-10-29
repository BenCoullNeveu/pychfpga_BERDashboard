"""
Utility functions to handle configuration files
"""
import logging
import re

from collections import Sequence, Mapping
from namespace import NameSpace, merge_dict
from core.icecore import load_yaml



def load_yaml_config(object_names, default_filename='config.yaml'):
    """
    Loads one or more elements from a YAML configuration file.

    Parameters:

        object_names (str or list of str): String or list of strings describing the name of a YAML
           files and objects to load.

            [filename :]object_name{.object_name} {[.]object_name{.object_name}}

           Name of objects are specified by preceding them with a semicolon.
           Object hierarchy is separated by '.'. An object starting with '.'
           starts at the same root note as the previous object.

        default_filename (str): Filename to use if no file is specified (no semicolon)

    Returns:
         A Python dictionary

    Examples::
        Yaml file *conf.yaml*::
            obj1:
                field11: 11
                obj11:
                    field111: 111
                    field112: 112
                obj12:
                    field121: 121
                    field122: 122
            obj2:
                field21: 21
                obj21:
                    field211: 211
                    field212: 212


        # Loading objects from default conig file
        load_yaml_config('obj1')  -> {field11: ..., obj11: ..., obj12: ...}
        load_yaml_config('obj1 obj2')  -> {field11: ..., obj11: ..., obj12: ..., field21: ..., obj21: ...}
        load_yaml_config('obj1.obj11 obj2')  -> {field111: ..., field112: ..., field21: ..., obj21: ...}
        load_yaml_config('obj1.obj11 .obj12')  -> {field111: ..., field112: ...,  field121: ..., field122:...}

        # With a specific filename
        load_yaml_config('conf.yaml:obj1 obj2')


    """
    # -------------------------------
    # Load YAML file
    # -------------------------------
    # The YAML file may contain any configuration data that will be
    # accessible by the user, which includes hardware maps that will be
    # extracted below


    if not object_names:
        return {}

    # If the objects are passed as a list of strings, combine those in a single string
    if not isinstance(object_names, str):
        object_names = ' '.join(object_names)  # Combine all strings into a single string

    config = {}
    logger = logging.getLogger(__name__)
    if not object_names:
        return config

    yaml_args = object_names.split(':')
    if len(yaml_args) > 2:
        raise ValueError('Only one filename can be specified')

    # yaml_filename = yaml_args[0] or default_filename

    # print yaml_filename
    if len(yaml_args) == 1: # if there is no semicolon, it's an object in the default filename
        yaml_filename = default_filename
        object_names = yaml_args[0]
    elif len(yaml_args) == 2: # if there was a semicolon, the first item is the filename, the rest are the object names in that file
        yaml_filename = yaml_args[0]
        object_names = yaml_args[1]
    object_names = [s for s in re.split('\s+|(=)', object_names) if s]
    logger.info('Loading YAML file %s' % (yaml_filename))
    # print 'Loading YAML file %s' % yaml_filename
    with open(yaml_filename, 'rb') as yamlfile:
        yaml = NameSpace(load_yaml(yamlfile))

    # self.hwm = None
    # current_root_node = yaml
    current_yaml_path = None
    current_config_path = None
    config = NameSpace()
    while object_names:
        #print('object_names = %s' % object_names)
        if len(object_names) > 2 and object_names[1] == '=':  # if this is an inline assignment
            #print('looking for assignment %s in config %r' % (object_names[0], config))
            (name, parent, obj) = config.findone(object_names[0], lastpath=current_config_path)
            child_index = name.rsplit('.', 1)[-1]
            parent[child_index] = type(obj)(object_names[2])
            object_names.pop(0)
            object_names.pop(0)
            object_names.pop(0)
            current_config_path = name
        else:
            (name, parent, obj) = yaml.findone(object_names.pop(0), lastpath=current_yaml_path)
            config.merge(obj)
            current_yaml_path = name

    # for yaml_object_path in object_names:
    #     yaml_path_items = yaml_object_path.split('.')
    #     if yaml_path_items[0]:  # If the path does not start with '.', restart from top
    #         current_root_node = yaml
    #     current_node = current_root_node
    #     for path_item in yaml_path_items:
    #         if path_item:
    #             if path_item in current_node:
    #                 current_root_node = current_node
    #                 current_node = current_node.get(path_item)
    #             else:
    #                 raise RuntimeError("YAML file loading error: Unknown object '%s'" % yaml_object_path)
    #     logger.info('Loading YAML elements from object %s' % (yaml_object_path))
    #     # print 'Loading YAML elements from object %s' % yaml_object_path

    #     # if isinstance(node, Session):
    #     #     self.hwm = self.yaml
    #     if not isinstance(current_node, dict):
    #         raise RuntimeError("Target element '%s' must be a dictionary" % yaml_object_path)
    #     # print 'merging', current_node, 'with', config
    #     config = merge_dict(current_node, config)
    return config

def validate_yaml_config(config, schema_file):
    print 'Loading Schema YAML file %s' % schema_file
    with open(schema_file, 'rb') as yamlfile:
        schema = load_yaml(yamlfile)

    def validate(config, schema):
        for key, info in schema.items():
            type_ = info['type']
            if key not in config:
                config[key] = get(schema, 'default', {})
            value = config[key]
            if isinstance(info, dict) and 'type' not in info:
                validate(config[key], schema[key])
                continue
            try:
                if type_ == 'integer':
                    assert isinstance(value, int) and not ((hasattr(info,'min') and value < info['min']) or (hasattr(info,'max') and value > info['max']))
                elif type_ == 'float':
                    assert isinstance(value, float) and not ((hasattr(info,'min') and value < info['min']) or (hasattr(info,'max') and value > info['max']))
                elif type_ == 'string':
                    assert isinstance(value, str)
                elif type_ == 'ip_addr':
                    socket.inet_aton(value)
                elif type_ == 'int_list':
                    assert isinstance(value, list) and all(isinstance(x, int) for x in value)
            except (AssertionError, socket.error):
                raise ValueError("Value for %s=%s failed the criteria %s" % (key, value, info) )

    validate(config, schema)
