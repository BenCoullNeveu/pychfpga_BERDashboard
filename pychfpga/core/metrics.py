"""
Provides a simplified object to handle Prometheus metrics.
"""

import time as time_
from .icecore import NameSpace

class Metrics(object):
    """ Simplified container to hold Prometheus Metrics.
    """
    def __init__(self):
        self.metrics = {}

    def items(self):
        return self.metrics.items()

    def add(self, metric_name, value=None, type=None , doc=None, time=None, **labels):
        """ Add a metric, a metric entry, or add all the metrics from another Metrics object.

        Parameters:

            metric_name (Metric or str): If `metric_name` is a `Metrics` instance, all the metric
               and metric entries are added to this object, with the labels in `labels` added to
               every metric. If if it a *str*, a new metric is created or information is added to
               the existing metric.

            value (float or int): If not None, a new entry with `time`, `value` and `labels` is added to the metric.

            time (int): time (ms since epoch) to be added to the entry stored when `value` is not None. If time is Node, the current time is used.

            \**labels: labels to be added to the entrystored when `value` is not None

            doc: documentation associated with the metric. Different docs cannot be associated with
                a metric. If not specified, there will not ``# HELP`` entry in the string output.

            type: type associated with the metric. Different types cannot be associated with
                a metric. If not specified, there will not ``# TYPE`` entry in the string output.
        """

        # If we pass a Metrics object, merge the metrics into this one.
        if isinstance(metric_name, Metrics):
            for met_name, met in metric_name.metrics.items():
                self.add(met_name, doc=met.doc, type=met.type)
                for entry in met.entries:
                    new_labels = dict(entry.labels.items() + labels.items())
                    self.add(met_name, value=entry.value, time=entry.time, **new_labels)
            return

        # get the metric from the dct, or create an empty one
        metric = self.metrics.setdefault(metric_name, NameSpace(type=None, doc=None, entries=[]))

        # Assign documentation if some is provided. It must be unique to the metric.
        if metric.doc and doc and metric.doc != doc:
            raise RuntimeError('Cannot assign different docs to metric %s' % metric_name)
        elif doc:
            metric.doc = doc

        # Assign metric type if some is provided. It must be unique to the metric.
        if metric.type and type and metric.type != type.upper():
            raise RuntimeError('Cannot assign different types to metric %s' % metric_name)
        elif type:
            metric.type = type.upper()

        # Add entric (value and labels) to the metric
        if value is not None:
            metric.entries.append(NameSpace(value=value, labels=labels, time=time or time_.time() * 1000))

    def  __str__(self):
        s = []
        for metric_name, m in self.metrics.items():
            if m.doc:
                s.append('# HELP %s %s\n' % (self.metric_name, self.doc))
            if m.type:
                s.append('# TYPE %s %s\n' % (self.metric_name, self.type))
            for entry in m.entries:
                labels = '{' + ','.join('%s="%s"' % (k, v) for k, v in entry.labels.items()) + '}' if entry.labels else ''
                s.append('%s%s %f %i\n' % (metric_name, labels, entry.value, entry.time))
        return ''.join(s)
