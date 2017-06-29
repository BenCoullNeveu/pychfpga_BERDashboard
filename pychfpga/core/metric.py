"""
Simplified library to handle metrics.
"""

import time

class Metric(object):
    def __init__(self, metric_name, value, type='UNDEFINED' , documentation=' No docs', **labels):
        self.metric_name = metric_name
        self.type = type.upper()
        self.doc = documentation
        self.labels = labels
        self.value = value
        self.time = time.time() * 1000
    def  __str__(self):
        return ('# HELP %s %s\n' % (self.metric_name, self.doc) +
               '# TYPE %s %s\n' % (self.metric_name, self.type) +
               '%s{%s} %f %i' % (self.metric_name, ','.join('%s="%s"' % (k,v) for k,v in self.labels.items()), self.value, self.time))

