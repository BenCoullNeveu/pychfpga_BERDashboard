import lxml.etree
import lxml.objectify
import lxml.html
import docutils.core
import inspect
import os

import matplotlib.pyplot as plt
import numpy as np
import StringIO
import base64
import urllib

__all__ = [
    "GROUP", "CASE",
    "TITLE", "DESCRIPTION", "DETAILS", "PASSED",
    "SUMMARY",
    "CONTEXT", "ITEM", "NAME", "VALUE",
    "P", "IMG", "A",
    "TestGroup",
    "IncompleteError",
    "PLOT"
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

# For "description", "details", and "summary", some HTML elements are useful
# for styling.
P = lxml.objectify.E.p
IMG = lxml.objectify.E.img
A = lxml.objectify.E.A


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

    def run(self, *args, **kwargs):
        '''Run this TestGroup and any of its children.

        Tests are discovered via test_list() (which you should override in a
        subclass.)
        '''

        passed = None

        for tc in self.test_list():
            if isinstance(tc, TestGroup):
                pf = tc.run(*args, **kwargs)
                self._docs.append(tc.document())
            else:
                (title, description) = self._document_from_docstrings(tc, inspect.getdoc(tc))

                results = tc(*args, **kwargs)
                if isinstance(results, bool):
                    annotations = PASSED(results)
                else:
                    annotations = list(results)  # *** allow returning a generator
                    pass_result = [x.text for x in annotations if x.tag == 'passed']
                    if len(pass_result) != 1:
                        raise RuntimeError('There must be one PASSED element in this test')
                    else:
                        pf = bool(pass_result[0])
                    # (pf, annotations) = (results[0], list(results[1:]))
                self._docs.append(CASE(*[
                    TITLE(title),
                    DESCRIPTION(*description),
                    # PASSED(pf),
                ] + annotations))
            passed = (pf if passed is None else passed and pf)

        self._passed = passed
        self._complete = True
        return passed

    def test_list(self):
        '''Returns a generator that provides tests in this TestGroup.

        Override this method to add tests.'''
        return
        yield

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

        if not self._complete:
            raise IncompleteError("Can't document an algorithm that "
                                  "hasn't completed yet!")

        # Grab information from DocStrings
        (title, description) = self._document_from_docstrings(self, inspect.getdoc(TestGroup))

        results = [
            TITLE(title),
            DESCRIPTION(*description),
            PASSED(self._passed),
        ]

        if self._context:
            results.append(CONTEXT(*[ITEM(NAME(k), VALUE(v))
                                   for (k,v) in self._context.items()]))

        if self._details:
            results.append(DETAILS(self._details))

        if self._docs:
            results.extend(self._docs)

        return GROUP(*results)

    def xml(self):
        '''Export as XML'''
        return lxml.etree.tostring(self.document(), pretty_print=True)

    def html(self, stylesheet=None):
        '''Export as HTML'''

        if stylesheet is None:
            stylesheet = os.sep.join(__file__.split(os.sep)[:-1]+['qc.xsl'])

        # Load the stylesheet that translates to HTML
        xslt = lxml.etree.parse(open(stylesheet))
        html_dom = lxml.etree.XSLT(xslt)(self.document())
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
        return 'data:image/png;base64,' + urllib.quote(base64.b64encode(io.buf))

def PLOT(caption='No Caption', format = 'png'):
    return DETAILS(
        P(caption),
        IMG(src=get_plot_as_uri(format=format))
    )

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab

