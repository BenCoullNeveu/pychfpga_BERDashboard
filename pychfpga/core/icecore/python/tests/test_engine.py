import lxml.etree
import lxml.objectify
import lxml.html
import docutils.core
import inspect
import os
import json
import sys
import traceback

from copy import deepcopy
import matplotlib.pyplot as plt
import numpy as np
import StringIO
import base64
import urllib
import datetime

__all__ = [
    "GROUP", "CASE",
    "TITLE", "DESCRIPTION", "DETAILS", "PASSED",
    "SUMMARY",
    "CONTEXT", "ITEM", "NAME", "VALUE",
    "P", "IMG", "A", "CODE", "PRE",
    "TestGroup",
    "IncompleteError",
    "PLOT", "load_html", "get_synopsis", "get_synopsis_from_xml", 'load_xml'
]


class IncompleteError(Exception):
    pass


# The following CAPITALIZED definitions correspond to XML node constructors
# using lxml.objectify.

# "context", "item", "name", "value" describe hardware setup associated with a
# test run.
CONTEXT = lxml.objectify.E.context
ITEM = lxml.objectify.E.item
NAME = lxml.objectify.E.name
VALUE = lxml.objectify.E.value

# "group", "case" store a heirarchy of test cases.
GROUP = lxml.objectify.E.group
CASE = lxml.objectify.E.case

# Both groups and cases have "title", "description", "details", "summary", and
# "passed" children
TITLE = lxml.objectify.E.title
DESCRIPTION = lxml.objectify.E.description
DETAILS = lxml.objectify.E.details
PASSED = lxml.objectify.E.passed
SUMMARY = lxml.objectify.E.summary
TESTNAME = lxml.objectify.E.testname
TESTPATH = lxml.objectify.E.testpath
TESTDATE = lxml.objectify.E.testdate
SYNOPSIS_DATA = lxml.objectify.E.synopsis_data


# For "description", "details", and "summary", some HTML elements are useful
# for styling.
P = lxml.objectify.E.p
IMG = lxml.objectify.E.img
A = lxml.objectify.E.A
CODE = lxml.objectify.E.code
PRE = lxml.objectify.E.pre


class TestGroup(object):
    '''Test title

    If you're seeing this text in documented outputs, it means someone has
    forgotten to properly document their test class.

    * They should fix it.
    * They can use `ReStructuredText <http://docutils.sourceforge.net/rst.html>`_
    '''
    def __init__(self, context={}):
        '''Create a TestGroup.

        The 'context' argument takes human-readable keys and values, and is
        used to describe hardware associated with a test run.
        '''

        self._context = context
        self._docs = []
        self._complete = False
        self._details = None
        self.etree = None
        self._passed = False
        self._complete = False

        self.FAILED = PASSED(False)
        self.PASSED = PASSED(True)

    def run(self, *args, **kwargs):
        '''Run this TestGroup and any of its children.

        Tests are discovered via test_list() (which you should override in a
        subclass.)
        '''
        try:
            self._run('', False, *args, **kwargs)
        except Exception:
            raise
        finally:
            self.etree = self.document()

        # return syn

    def _run(self, testpath, skip, *args, **kwargs):
        '''Run this TestGroup and any of its children and use the provided test path to name tests hierarchically.
        '''
        self._testpath = testpath + ('.' if testpath else '') + self.__class__.__name__
        passed = None
        for tc in self.test_list():
            if isinstance(tc, TestGroup):
                try:
                    pf = tc._run(self._testpath, skip, *args, **kwargs)
                except Exception as exception:
                    pf = False
                    raise exception
                self._docs.append(tc.document())
            else:
                testpath = self._testpath + '.' + tc.__name__
                (title, description) = self._document_from_docstrings(tc, inspect.getdoc(tc))
                if skip:
                    results = [PASSED('Skipped'), SUMMARY('This test case was skipped due to previous exception')]
                else:
                    results = tc(*args, **kwargs)  # obtain the generator
                    if isinstance(results, bool):  # if not a generator
                        results = [PASSED(results)]
                pf = []  # list of the value of pass/failed objects that were yielded
                annotations = []
                exception = None
                try:
                    for r in results:
                        if isinstance(r, bool):
                            r = PASSED(r)
                        if not hasattr(r, 'tag'):
                            print '%s yielded %r, converting into DETAILS' % (testpath, r)
                            r = DETAILS(str(r))
                        if r.tag == 'passed':
                            pf.append(r.text)
                        annotations.append(r)
                    if not len(pf):
                        raise RuntimeError('There must be at least one PASSED element in %s' % testpath)
                    else:
                        pf = all([bool(p) for p in pf])  # all PASSED fields must be true
                except Exception as exception:
                    annotations.extend([
                        PASSED(False),
                        SUMMARY('Exception was raised!'),
                        DETAILS('This test case failed with the following Exception: %s' % exception),
                        DETAILS('Traceback:'),
                        DETAILS(CODE(PRE('\n'.join(self.get_traceback()))))]
                        )
                        # [DETAILS(P(tb)) for tb in self.get_traceback()])
                    skip = True
                # (pf, annotations) = (results[0], list(results[1:]))
                self._docs.append(CASE(*[
                    TESTNAME(tc.__name__),
                    TESTPATH(testpath),
                    TESTDATE(datetime.datetime.now().isoformat()),
                    TITLE(title),
                    DESCRIPTION(*description),
                ] + annotations))
                if exception:
                    raise

            passed = (pf if passed is None else passed and pf)

        self._passed = passed
        self._complete = True
        return passed

    def test_list(self):
        '''Returns a iterable (a generator or a list) that enumerates the methods to be called in this TestGroup.

        Override this method to add tests.'''
        return []

    def get_traceback(self):
        """ Return a compact traceback message as a list of strings that is
        convenient for loging purposes.

        This must be called only after an exception has occured.
        """
        (exception_type, exception_args, exception_tb) = sys.exc_info()
        tb = traceback.extract_tb(exception_tb)
        tracebackString = []
        for (filename, line, fn, code) in tb:
            tracebackString.append('in %s from .../%s' % (fn + '(...)', os.path.split(filename)[1]))
            tracebackString.append('---> %5i      %s' % (line, code))
        tracebackString.append('%r' % exception_args)
        return tracebackString

    @staticmethod
    def _document_from_docstrings(thing, default):
        '''Try to convert DocStrings into a (title, description) tuple.'''

        # Grab information from DocStrings
        doc = inspect.getdoc(thing) or default
        title = doc.splitlines()[0]
        description = '\n'.join(doc.splitlines()[1:])

        # Markup to HTML
        title = docutils.core.publish_parts(title, writer_name='html')['body']
        description = docutils.core.publish_parts(description, writer_name='html')['body']

        # Markupify and parse into XHTML
        title = lxml.html.fromstring(title)
        description = lxml.html.fragments_fromstring(description)

        return (title, description)

    def document(self):
        '''Compile this algorithm's documentation into an etree GROUP.'''

        # if not self._complete:
        #     raise IncompleteError("Can't document an algorithm that "
        #                           "hasn't completed yet!")

        # Grab information from DocStrings
        (title, description) = self._document_from_docstrings(self, inspect.getdoc(TestGroup))

        results = [
            TESTNAME(self.__class__.__name__),
            TESTPATH(self._testpath),
            TESTDATE(datetime.datetime.now().isoformat()),
            TITLE(title),
            DESCRIPTION(*description),
            PASSED(self._passed),
        ]

        if self._context:
            results.append(CONTEXT(*[ITEM(NAME(k), VALUE(v))
                                   for (k, v) in self._context.items()]))

        if self._details:
            results.append(DETAILS(self._details))

        if self._docs:
            results.extend(self._docs)

        return GROUP(*results)

    def synopsis(self):
        if self.etree is None:
            raise RuntimeError('The test has not been run yet')
        return get_synopsis(self.etree)

    def synopsis_as_strings(self):
        syn = self.synopsis()
        col_width = [0, 0, 0, 0]
        for item in syn:
            for (i, field) in enumerate(item):
                    col_width[i] = max(col_width[i], len(str(field)))
        format_ = '| ' + ' | '.join('%%-%is' % width for width in col_width) + ' |'

        return [format_ % item for item in syn]

    def xml(self):
        '''Export as XML, with embedded XSL stylesheet so the browser can show the formatted data'''
        if self.etree is None:
            raise RuntimeError('The test has not been run yet')

        # get the XSL style sheet
        stylesheet = os.sep.join(__file__.split(os.sep)[:-1]+['qc.xsl'])
        xsl = lxml.etree.parse(open(stylesheet))

        # Create an empty XML document
        xml = lxml.etree.XML(
            '<?xml version="1.0" encoding="UTF-8"?> \n'
            '<!DOCTYPE root [<!ATTLIST xsl:stylesheet id ID  #REQUIRED>]> \n'
            '<?xml-stylesheet type="text/xsl" href="#xslt"?>\n'
            '<root></root>\n')
        xml = lxml.etree.ElementTree(xml)

        # Get the root object of the empty document
        root = xml.getroot()
        # Add the XSL stylesheet to root
        root.append(xsl.getroot())
        # Add the data to root
        root.append(deepcopy(self.etree)) #use deepcopy because this seems to change the original object

        return lxml.etree.tostring(xml, pretty_print=True)

    def write_xml(self, filename):
        # Write transformed HTML to disk.
        with open(filename, "w") as f:
            f.write(self.xml())

    def html(self, stylesheet=None):
        '''Export as HTML'''

        if self.etree is None:
            raise RuntimeError('The test has not been run yet')

        if stylesheet is None:
            stylesheet = os.sep.join(__file__.split(os.sep)[:-1]+['qc.xsl'])

        # Load the stylesheet that translates to HTML
        xslt = lxml.etree.parse(open(stylesheet))
        html_dom = lxml.etree.XSLT(xslt)(self.etree)
        return lxml.etree.tostring(html_dom, pretty_print=True)

    def write_html(self, filename):
        # Write transformed HTML to disk.
        with open(filename, "w") as f:
            f.write(self.html())


def get_plot_as_uri(format='png'):
        ''
        io = StringIO.StringIO()
        plt.gcf().savefig(io, format=format)
        io.seek(0)
        return ('data:image/%s;base64,' % format +
                urllib.quote(base64.b64encode(io.buf))
                )

def PLOT(caption='No Caption', format='png'):
    return DETAILS(
        P(caption),
        IMG(src=get_plot_as_uri(format=format))
    )


def load_html(filename):
    with open(filename) as file_:
        f = file_.read()
    return lxml.objectify.fromstring(f)


def load_xml(filename):
    with open(filename) as file_:
        t = lxml.etree.parse(file_)
    return t


def get_synopsis_from_xml(filename):
    e = load_html(filename)
    return get_synopsis(e)

def get_synopsis(etree):
    return [(str(x.testdate), str(x.testpath), str(x.passed), str(x.summary) if hasattr(x, 'summary') else '') for x in etree.iter(['case', 'group'])]
# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
