""" Logging support functions
"""
import os
import logging
import collections

class NameSpace(object):
    """ Wraps an iterable (list, dict) and any of its elements such that failed attribute accesses are tried as item access.
    """
    def __init__(self, *args, **kwargs):
        if not args:
            obj = kwargs
        elif len(args)>1 or kwargs:
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
        attrs = dir(type(self)) + vars(self).keys() + dir(self._obj)
        return attrs


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

        new_loggers[new_logger_name] = logger_config

    dict_config.loggers = new_loggers

    # print 'new loggers=', new_loggers

    # register the existing handlers for each logger
    old_handlers = {}
    for logger_name in dict_config.loggers:
        old_handlers[logger_name] = logging.getLogger(logger_name).handlers




    logging.config.dictConfig(dict_config)

    new_handlers = {}
    for logger_name in dict_config.loggers:
        new_handlers[logger_name] = [handler for handler in logging.getLogger(logger_name).handlers if handler not in old_handlers[logger_name]]

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
                        'format': "%(asctime)s %(levelname)s %(name)s.%(funcName)s() %(filename)s:%(lineno)d>> %(message)s", 
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
