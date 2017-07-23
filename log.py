""" Logging support functions
"""
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
    """ get a logger whose hiearchical name elements are provided in `names`.

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
            return x.__class__.__name__

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


def setup_logging(dict_config={}, log_levels={}, **kwargs):
    """
    """


    dict_config = NameSpace(dict_config)
    log_levels = NameSpace(log_levels or {})

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
    for logger_name, logger_config in dict_config.loggers.items():
        if 'level' in logger_config and isinstance(logger_config.level, basestring):
            logger_config.level = logger_config.level.upper()


    #print dict_config
    logging.config.dictConfig(dict_config)

def stop_logging(dict_config):
    """
    Delete all handles for the loggers defined in the loging config.
    """

    dict_config = NameSpace(dict_config)
    for logger_name in dict_config.loggers:
        logger = logging.getLogger(logger_name)
        logger.handlers = []  # clear all existing handlers for that logger


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
