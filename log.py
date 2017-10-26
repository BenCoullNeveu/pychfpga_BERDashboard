""" Logging support functions
"""
import os
import logging
import collections
import re
import yaml

re_dot = r"\."

class NameSpace(object):
    """ Wraps an iterable (list, dict) and any of its accessed elements such that failed
    attribute accesses are tried as item access.

    Usage:

    n = NameSpace(a=1, b=2, c=dict(e=4, f=5))
    print n.c.e

    d=dict(a=1, b=2, c=dict(e=4, f=5)
    n = NameSpace(d)
    n2 = NameSpace(n)
    print n.c.e


    """
    def __init__(self, *args, **kwargs):
        if not args:
            obj = kwargs
        elif len(args) > 1 or kwargs:
            raise TypeError('Specify either a single object or keyword list')
        elif isinstance(args[0], NameSpace):
            obj = args[0]._obj
        else:
            obj = args[0]
        object.__setattr__(self, '_obj', obj)

    def _to_namespace(self, x):
        if isinstance(x, collections.Iterable) and not isinstance(x, basestring):
            return NameSpace(x)
        else:
            return x

    def __getattr__(self, name):
        try:
            return self._to_namespace(getattr(self._obj, name))
        except AttributeError:
            if hasattr(self._obj, '__getitem__'):
                return self._to_namespace(self._obj[name])
            else:
                raise

    def __setattr__(self, name, value):
        try:
            setattr(self._obj, name, value)
        except AttributeError:
            if hasattr(self._obj, '__getitem__'):
                self._obj[name] = value
            else:
                raise

    def __getitem__(self, name):
            return self._to_namespace(self._obj[name])

    def __setitem__(self, name, value):
            self._obj[name] = value

    def __delitem__(self, name):
            del self._obj[name]

    def __iter__(self):
        for x in self._obj:
            yield self._to_namespace(x)

    def iteritems(self):
	for (k,v) in self._obj.iteritems():
            yield (k, self._to_namespace(v))

    def itervalues(self):
        for v in self._obj.itervalues():
            yield self._to_namespace(v)

    def items(self):
       return list(self.iteritems())

    def values(self):
        return list(self.itervalues())

    def __len__(self):
        return len(self._obj)

    def __contains__(self, x):
        return x in self._obj

    def __str__(self):
        return str(self._obj)

    def __repr__(self):
        return 'NameSpace(%r)' % (self._obj, )

    def __dir__(self):
        attrs = set(dir(type(self)) + vars(self).keys() + dir(self._obj) +
            self._obj.keys() if isinstance(self._obj, collections.Mapping) else [] )
        return list(attrs)

    def as_dict(self):
        return self._obj

        # def todict(v):
        #     if isinstance(v, collections.Mapping):
        #         return {k: todict(i) for k, i in v.items()}
        #     elif isinstance(obj, collections.Sequence) and not isinstance(obj, basestring):
        #         return [todict(i) for i in v]
        #     else:
        #         return v
        # return todict(self)

    def as_yaml(self):
        return yaml.safe_dump(self.as_dict(), default_flow_style=False)


    def iterfind(self, pattern='**', lastpath='', search_lists=False, verbose=0):
        """Generator that yield the full paths to every elements in obj, depth-first.

        Parameters:

            pattern (str): pattern to search for

            lastpath (str): base path used with relative paths.

            search_list (bool): If true, lists items and content and their contnts will be searched.
                Can significantly slow down searches if a cross-level wildcard is used early in the
                path.

        """

        while pattern.startswith('.'):
            lastpath = lastpath.rsplit('.', 1)[0]
            pattern = pattern[1:]

        if lastpath:
            pattern = lastpath + '.' + pattern

        # build the full path regular expression
        for sub, repl in (('**', '::'), ('.', re_dot), ('[', re_dot +r'\['), (']', r'\]'), ('*', '[^.]*'), ('::', '.*?')):
            pattern = pattern.replace(sub,repl)

        # if verbose:
        #     print('Full pattern is %s' % (pattern + '$'))
        full_pattern = re.compile(re_dot + pattern + '$') # to be used with .match()

        # Compute the pattern that will be used to determine if we descend into sub-elements.
        # It will save a lot of computational time if we don't have to descend into all possible branches

        # Stop path at wildcards that cross hierarchical levels. We have to check all the way down anyway once we got one...
        if '.*?' in pattern:
            pattern = pattern.split('.*?')[0] + '.*?'

        re_index = re.compile(r'\[[^\]]*\]$')
        re_int_index = re.compile(r'\[(\d+)\]$')

        split_pattern = pattern.split(re_dot)
        not_wild = [int('*' not in s) for s in split_pattern]
        is_int_index = [re_int_index.match(s) for s in split_pattern]
        int_index = [int(r.group()) if r else None for r in is_int_index]

        # if verbose:
        #     print("Split pattern elements are %s\n-------------" % (','.join("'%s'" % s for s in split_pattern)))

        # Mapping = collections.Mapping
        Sequence = collections.Sequence
        def paths(prefix, obj, level=0):
            """
            Search a specific node `obj` for the target pattern.

            Parameters:
                obj (dict): An object to get paths from.

                prefix (str): prefix to add to the names found in the current object. Used for recursion.

                level (int): The index of the pattern element we are now looking for. Used to accelerate searches when possible.
            """
            if hasattr(obj, 'iteritems'):# and isinstance(obj, Mapping): # the hasattr() test is much faster than isinstance. It is significantly faster not to check isinstance at all.
                lpat = split_pattern[level]

                if lpat in obj: # obj[lpat] instead of all obj's children if lpat is found in obj. This really helps only when we end up going down long lists
                    new_prefix = '%s.%s' % (prefix, lpat) # if not isinstance(child_prefix, str) else child_prefix)
                    child_obj = obj[lpat]
                    if full_pattern.match(new_prefix):
                        yield new_prefix, child_obj #self._to_namespace(child_obj) 28 ms for _to_namespace()
                    for item in paths(new_prefix, child_obj,  level + not_wild[level]):
                        yield item
                else: # test every items if the dict, and their children
                    for (child_prefix, child_obj) in obj.iteritems(): #9 ms gain by using obj.iteritems directly
                        new_prefix = '%s.%s' % (prefix, child_prefix) # if not isinstance(child_prefix, str) else child_prefix)
                        if full_pattern.match(new_prefix):
                            yield new_prefix, child_obj #self._to_namespace(child_obj) 28 ms for _to_namespace()
                        for item in paths(new_prefix, child_obj, level + not_wild[level]):
                            yield item
            elif search_lists and not isinstance(obj, basestring) and isinstance(obj, Sequence):
                index = int_index[level]
                if index is not None:
                    new_prefix = '%s.[%i]' % (prefix, index) # if not isinstance(child_prefix, str) else child_prefix)
                    child_obj = obj[index]
                    yield new_prefix, child_obj
                    for item in paths(new_prefix, child_obj, level + not_wild[level]):
                        yield item
                else:
                    for (index, child_obj) in enumerate(obj):
                        new_prefix = '%s.[%i]' % (prefix, index) # if not isinstance(child_prefix, str) else child_prefix)
                        if full_pattern.match(new_prefix):
                            yield new_prefix, child_obj #self._to_namespace(child_obj) 28 ms for _to_namespace()
                        for item in paths(new_prefix, child_obj, level + not_wild[level]):
                            yield item

        return ((k[1:].replace('.[', '['), self._to_namespace(v)) for k, v in paths('', self._obj))

    def findall(self, pattern, lastpath=''):
        return dict(self.iterfind(pattern, lastpath))

    def findone(self, pattern, lastpath=''):
        gen = self.iterfind(pattern, lastpath)
        res = next(gen, None)
        if res is None:
            raise AttributeError('Cannot find pattern %s' % pattern)
        if next(gen, None) is not None:
            raise AttributeError('More than one entry matches the pattern %s' % pattern)
        return res

def get_logger(*names):
    """ get a logger whose hierarchical name elements are provided in `names`.

    If no names are provided, the root logger is returned.

    Examples:

        get_logger(): returns root logger
        get_logger(__package__): return the logger corresponding to the package in which the current module is located
        get_logger(__name__): return the logger for the current package.module
        get_logger(__name__, self): return the logger for the current package.module.class_name
        get_logger(__name__, self, 'my_method'): return the logger for the current package.module.class_name

    Notes:
        - Anywhere in a module, the global variable ``__package__`` represents the full hierarchical name of the package in which the module is located.
        - Anywhere in a module, the global variable ``__name__`` represents the full hierarchical name of the packageof the module followrd by the module name.

    """
    def getname(x):
        if isinstance(x, str):
            return x
        else:
            cls = x.__class__
            return cls.__module__ + '.' + cls.__name__

    if not names:
        return logging.getLogger()
    else:
        logger = logging.getLogger(getname(names[0]))
        for name in names[1:]:
            logger = logger.getChild(getname(name))
        #print('created logger %s' % logger.name)
        logger.disabled = False
        return logger

# def get_class_logger(class_instance):
#     """ Return a logger named "full_module_name.class_name"

#     Includes the package name.

#     """
#     return get_logger(class_instance.__class__.__module__, class_instance.__class__.__name__)


def get_parent_logger(module_name):
    """
    Return the parent logger of the specified module.

    If the module is not imported as part of a package (i.e. this module is named 'ch_master'
    instead if 'ch_acq.ch_master'), then return the root logger.

    Usage::

        log.get_parent_logger(__name__)
    """

    return logging.getLogger(module_name.rsplit('.', 1)[0] if '.' in module_name else '')



# def setup_parent_logger(module_name,
#                         stdout_log_level=None,
#                         stderr_log_level=None,
#                         syslog_log_level=None,
#                         file_log_level=None,
#                         log_filename=None):
#     """
#     Configure the logging parameters for the parent logger of this module.

#     This configures the logging for all modules in the same packages as module_name.
#     """

#     setup_logger(get_parent_logger(module_name),
#                         stdout_log_level=stdout_log_level,
#                         stderr_log_level=stderr_log_level,
#                         syslog_log_level=syslog_log_level,
#                         file_log_level=file_log_level,
#                         log_filename=log_filename)


def setup_logging(dict_config={}, log_levels={}, base_package_name=None, script_name=None, actual_package_name=None, **kwargs):
    """

    Parameters:

        base_package_name (str): name of the package that contains all the loggers in the config file.

        actual_package_name (str): Actual name of the packages that correspond to the base package name, as
            returned by __package__. This will be used to adjust the full logger names to account for the
            package name. This is typically __name__.rpartition('.')[0], as __package__ is not set consistently.

        script_name (str): names of the module that is executed as a script, if any. If a logger with that name exists, a
            copy of that logger will be added under the name "__main__" (because when modules are
            executed as scripts, ``__name___ = "__main__"``).



    Logger names:
        ch_acq
        ch_acq.ch_master
        ch_acq.pychfpga.fpga_array

    We want to logging to be set-up properly for this package whether the module is used as a script
    or is imported as part of another parent package. It is assumed that loggers are created with
    the name  provided by ``__name__``. However, ``__name__`` changes depending on how it is loaded.
    Taking ch_master module as an example, ``__name__`` take the following values:

       __main__ if ch_master is launched as a script
       ch_master if loaded from ch_acq
       ch_acq.ch_master if loaded with from ch_acq import ch_master
       app_pkg.ch_acq.ch_master if nested more deeply

    For this reason, logger names need to be modufied by doing the following modifications:
    logger names modifications:
        - strip the package prefix used in the config
        - create __main__ logger as a copy of the base module, in case the base module is executed as a script
        - prepend all the logger names with the actual package path

    To do so, we need the following information:
        - base package used in the config ('ch_acq' or extracted from __file__)
        - name of module called as script
        - actual package prefix (__package__= 'app_pkg.ch_acq', __name__ = 'app_pkg.ch_acq.ch_master')

    This can be provided by two information:
        - base_package_name = 'ch_acq' (constant). Base package. Could be taken from the config file.
        - module_name = __package__ (__main__ if run as script, ch_master if from the package, ch_acq or my_pkg.ch_acq if imported from a parent
        - script_name = 'ch_master' (constant). Could be taken from the config file.



    """

    # print 'setting up logger with', base_package_name, actual_package_name, script_name
    dict_config = NameSpace(dict_config)
    log_levels = NameSpace(log_levels or {})

    # Add the version number if non-existent
    if 'version' not in dict_config:
        dict_config.version = 1

    # If there are log_level shortcuts, apply those log levels to the corresponding handler
    for handler_name, log_level in log_levels.items():
            if handler_name in dict_config.handlers:
                dict_config.handlers[handler_name]['level'] = log_level

    # if there are filenames arguments in handlers, process the name with format to add pathname
    for handler_name, handler_config in dict_config.handlers.items():
        if 'level' in handler_config and isinstance(handler_config.level, basestring):
            handler_config.level = handler_config.level.upper()

        filename = handler_config.get('filename', None)
        if isinstance(filename, str) and '%(' in filename:
            handler_config.filename = filename % kwargs

    # fix the case of the logging levels to uppercase
    for logger_name, logger_config in dict_config.loggers.items():
        if 'level' in logger_config and isinstance(logger_config.level, basestring):
            logger_config.level = logger_config.level.upper()


    # Add a logger named __main__ in case the module is run as as script
    if script_name in dict_config.loggers:
        prefix, sep, name = script_name.rpartition('.')
        new_logger_name = prefix + sep + '__main__'
        dict_config.loggers[new_logger_name] = dict_config.loggers[script_name]
        #print('Added logger %s to process logs from %s' % (new_logger_name, script_name))
    # fix the logger names for the current package
    new_loggers = {}
    for logger_name, logger_config in dict_config.loggers.items():

        new_logger_name = logger_name

        # Remove the base package prefix
        if base_package_name:
            if logger_name == base_package_name:
                new_logger_name = ''
            elif logger_name.startswith(base_package_name + '.'):
                new_logger_name = logger_name[(len(base_package_name) + 1): ]

        # prepend actual package path
        if actual_package_name:
            new_logger_name = actual_package_name + (('.' + new_logger_name) if new_logger_name else '')
        #print('Converted logger name from %s to %s' % (logger_name, new_logger_name))
        new_loggers[new_logger_name] = logger_config

    dict_config.loggers = new_loggers

    #print 'new loggers=', new_loggers

    # register the existing handlers for each logger
    old_handlers = {}
    for logger_name in dict_config.loggers:
        old_handlers[logger_name] = logging.getLogger(logger_name).handlers


    print('new loggingconfig is: %r' % dict_config)

    logging.config.dictConfig(dict_config)

    new_handlers = {}
    for logger_name in dict_config.loggers:
        logger = logging.getLogger(logger_name)
        logger.disabled = False # re-enable the logger if is was disabled by a previous config. dictConfig() doen not do that
        new_handlers[logger_name] = [handler for handler in logger.handlers if handler not in old_handlers[logger_name]]

    return new_handlers

def stop_logging(new_handlers):
    """
    Delete the specified handlers for the loggers defined in new_handlers.


    """

    for logger_name, handlers in new_handlers.items():
        logger = logging.getLogger(logger_name)
        for handler in handlers:
            if handler in logger.handlers:
                logger.handlers.delete(handler)  # remove the handlers that were added for that logger

def setup_basic_logging(level='INFO'):

    DEFAULT_LOGGING = {
        'formatters': {
             'std': {
                 'format': "%(asctime)s %(levelname)s %(name)s: %(message)s",
                 'datefmt': "%H:%M:%S" },
              },
        'handlers': {
            'stderr': {'class': 'logging.StreamHandler', 'formatter': 'std', 'level': level}
            },
        'loggers': {
            '': {'handlers': ['stderr'], 'level': level}  # root logger

            }
        }
    setup_logging(DEFAULT_LOGGING)




# def setup_logger(logger,
#                  stdout_log_level=None,
#                  stderr_log_level=None,
#                  syslog_log_level=None,
#                  file_log_level=None,
#                  log_filename=None):
#     """
#     Configure the logging parameters for the specified logger.

#     All logging messages from ch_master classes, pychfpga package modules, raw_acq etc... are named
#     hierarchically with their module name and trickle down to the ``ch_acq`` logger. We configure
#     this `ch_acq` logger to have the desired formatting.

#     """
#     if isinstance(logger, str):
#         logger = logging.getLogger(logger)

#     logger.setLevel(logging.DEBUG) # pass all messages to the handlers
#     logger.handlers = []  # clear all existing handlers
#     formatter = logging.Formatter(self.LOG_FORMAT, self.LOG_DATE_FORMAT)

#     def add_handler(h, log_level):
#         h.setFormatter(formatter)
#         level = log_level if isinstance(log_level, int) else log_level.upper()
#         h.setLevel(level)
#         logger.addHandler(h)

#     # Stderr logger
#     if stdout_log_level is not None:
#         add_handler(logging.StreamHandler(sys.stdout), stdout_log_level)
#     if stderr_log_level is not None:
#         add_handler(logging.StreamHandler(sys.stderr), stderr_log_level)
#     if syslog_log_level is not None:
#         add_handler(logging.handlers.SysLogHandler(), syslog_log_level)
#     if file_log_level is not None:
#         add_handler(logging.FileHandler(log_filename), file_log_level)
#         self.log.info("Now logging to \"%s\"." % log_filename)


# def stop_logger(logger):
#     if isinstance(logger, str):
#         logger = logging.getLogger(logger)
#     logger.info("Removing all loggers")
#     logger.handlers = []  # just wipe all handlers


# def add_parent_file_logger(self,log_filename):

#     # Start writing to a log file in this directory.
#     logger = self.get_parent_logger()
#     formatter = logging.Formatter(self.LOG_FORMAT, self.LOG_DATE_FORMAT)
#     handler = logging.FileHandler(log_filename)
#     handler.setFormatter(formatter)
#     logger.addHandler(handler)
if __name__=='__main__':
    pass