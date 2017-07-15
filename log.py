""" Logging support functions
"""
import logging


def get_logger(*names):
    if not names:
        return logging.getLogger()
    else:
        logger = logging.getLogger(names[0])
        for name in names[1:]
            logger=logger.getChild(name)
        return logger

def get_class_logger(class_instance):
    """ Return a logger named "full_module_name.class_name"

    Includes the package name.

    """
    return get_logger(class_instance.__class__.__module__, class_instance.__class__.__name__)


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

def setup_logger(logger,
                 stdout_log_level=None,
                 stderr_log_level=None,
                 syslog_log_level=None,
                 file_log_level=None,
                 log_filename=None):
    """
    Configure the logging parameters for the specified logger.

    All logging messages from ch_master classes, pychfpga package modules, raw_acq etc... are named
    hierarchically with their module name and trickle down to the ``ch_acq`` logger. We configure
    this `ch_acq` logger to have the desired formatting.

    """
    if isinstance(logger, str):
        logger = logging.getLogger(logger)

    logger.setLevel(logging.DEBUG) # pass all messages to the handlers
    logger.handlers = []  # clear all existing handlers
    formatter = logging.Formatter(self.LOG_FORMAT, self.LOG_DATE_FORMAT)

    def add_handler(h, log_level):
        h.setFormatter(formatter)
        level = log_level if isinstance(log_level, int) else log_level.upper()
        h.setLevel(level)
        logger.addHandler(h)

    # Stderr logger
    if stdout_log_level is not None:
        add_handler(logging.StreamHandler(sys.stdout), stdout_log_level)
    if stderr_log_level is not None:
        add_handler(logging.StreamHandler(sys.stderr), stderr_log_level)
    if syslog_log_level is not None:
        add_handler(logging.handlers.SysLogHandler(), syslog_log_level)
    if file_log_level is not None:
        add_handler(logging.FileHandler(log_filename), file_log_level)
        self.log.info("Now logging to \"%s\"." % log_filename)


def stop_logger(logger):
    if isinstance(logger, str):
        logger = logging.getLogger(logger)
    logger.info("Removing all loggers")
    logger.handlers = []  # just wipe all handlers


# def add_parent_file_logger(self,log_filename):

#     # Start writing to a log file in this directory.
#     logger = self.get_parent_logger()
#     formatter = logging.Formatter(self.LOG_FORMAT, self.LOG_DATE_FORMAT)
#     handler = logging.FileHandler(log_filename)
#     handler.setFormatter(formatter)
#     logger.addHandler(handler)
