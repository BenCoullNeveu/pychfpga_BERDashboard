""" Nose plugin and utilities used to store, process and publish high quality test reports.



TODO:
    150612 JFC: - Add command line option to set the output filename(s) for XML and RST xreport.xsl
                - Handle when test targets are missing
                - Improve XML and RST report structure
                   - Add test run synopsis table with hyperlinks
                   - use different nodes for  output, Error/Failures, Logs so we can have different colors and make parsing easier
                   - Add context, summary and synopsis tables to rST reports
                - Add logs to report
                - Add a way for a test to provide output in restructured text. We may have to store a HTML version of it in a separate node for XML view.
                - Have attachment links renamed at the time of saving so we don't have to know the name of the Rst file when the document is being built.
                - Capture system exit message (when argparse.parse generates an error in the test suites)
                - Add xr.table() to generate nice tables. XML template will have to deal with it.
                - Add xr.rst_on() and xr.rst_off() to allow standard output to be parsed as restructuredText by default without having to use the xr.rst() command.
"""
import traceback
import sys
import os
import logging
import nose
from StringIO import StringIO
from nose.plugins import Plugin
import textwrap
import lxml.etree
import lxml.objectify
import lxml.html
import docutils.core
import inspect
from copy import deepcopy
import matplotlib.pyplot as plt
# import numpy as np
import base64
import urllib
import datetime


#------------------------------------------------
# XML nodes
#------------------------------------------------
# These nodes are used
# "group", "case" store a herarchy of test cases.
GROUP = lxml.objectify.E.group  # Contains all data from a nose 'context' (package, module, class, generator)
CASE = lxml.objectify.E.case # Contains all data from a nose 'testcase' (function, method)

CONTEXT = lxml.objectify.E.context  # Wraps a number of ITEMs that describe context information on the test. The ITEM elements are meant to be converted into a table.
ITEM = lxml.objectify.E.item # Represents a table row. Contains a NAME and a VALUE node.
NAME = lxml.objectify.E.name
VALUE = lxml.objectify.E.value


# Both GROUP and CASE can have the following children
TITLE = lxml.objectify.E.title  # Name of the test shown as header and in summary tables
DESCRIPTION = lxml.objectify.E.description  # Description of the test, taken from the docstring
DETAILS = lxml.objectify.E.details # test results (captured output and error messages)
PASSED = lxml.objectify.E.passed  # Pass/fail status of the current GROUP or CASE
SUMMARY = lxml.objectify.E.summary # Pass/fail short informative message, shown in summary tables
TESTNAME = lxml.objectify.E.testname  # Current test name
TESTPATH = lxml.objectify.E.testpath  # Hierarchical test name
TESTDATE = lxml.objectify.E.testdate  # Current test date & time
TESTARGS = lxml.objectify.E.testargs  # Current test arguments
SYNOPSIS_DATA = lxml.objectify.E.synopsis_data

#  HTML elements that can be useful for styling "description", "details", and
#  "summary"
P = lxml.objectify.E.p  # Paragraph
A = lxml.objectify.E.A  # Hyperlink
B = lxml.objectify.E.b  # boldface
CODE = lxml.objectify.E.code
PRE = lxml.objectify.E.pre  # preformatted code (keep spaces and newlines)
FIGURE = lxml.objectify.E.figure  # Contains IMG and FIGCAPTION nodes
IMG = lxml.objectify.E.img  # Image
FIGCAPTION = lxml.objectify.E.figcaption

def CONTEXT_TABLE(dict):
    """ Build a context table out of a dictionary """
    return CONTEXT(*[ITEM(NAME(k), VALUE(v))
                       for (k, v) in dict.items()])


"""
XML Schema
<group> # Test run
    <group> # Context: Module/package
        <testname>
        <testpath>
        <testdate>
        <title>
        <description>
            <details>, <details> ...
        <passed>
        <context>
        <case> # function
            <testname>
            <testpath>
            <testdate>
            <title>
            <description>
                <details>, <details> ...
            <passed>
            <details> or <figure>
            ...
            <details> or <figure>
        ...
        <case>
            ...
        <group> # Context: generator or class
            ...
    <details> # Final pass/fail results
"""

# ---------------------------------------------------------
# Utility attributes and functions availalable to the tests
# ---------------------------------------------------------



class XReport(Plugin):
    """Nose plugin the capture all test data and test results and package it
    into a queryable XML test data file.

    The XML test data embeds an XSLT template that make it directly viewable
    by browsers as a structured report just by opening it. The test data can
    also be published as reStructuredText or any other format supporteed by
    the docutils library.

    Xreport will capture all ``nosetests`` command-line arguments after the --xargs
    parameter and make them available to unittest.TestCase instances and modulein order
    to parametrize the tests from the command line.

    Plots generated by matplotlib can also be embedded in the test data and
    will be correctly rendered in all output formats.
    """
    instance = None  # Used to make sure we only ever run one instance of the plugin
    name = 'xreport'
    score = 2 # run late so we can capture all stdout and all remaining command line arguments

    xargs = []

    @classmethod
    def _no_plugin(cls, feature):
        raise Warning('The Xreport plugin is not active. %s will be ignored' % feature)

    @classmethod
    def insert_plot(cls, *args, **kwargs):
        if cls.instance:
            cls.instance._insert_plot(*args, **kwargs)
        else:
            cls._no_plugin('Plots')

    @classmethod
    def output(cls, message):
        if cls.instance:
            cls.instance._output(message)
        else:
            print message

    @classmethod
    def input(cls, message):
        return raw_input(message)

    @classmethod
    def flush(cls):
        if cls.instance:
            cls.instance._flush()

    @classmethod
    def rst(cls, message):
        if cls.instance:
            cls.instance.pprint(message)
        else:
            print message

    def __init__(self):
        super(XReport, self).__init__()
        self.stdout = []
        self._buf = None
        self.etree = GROUP()
        self.node_tail = [self.etree]
        self.node_name = []
        self.enabled = True
        self.original_stdout = sys.stdout
        self.stream = sys.stdout
        self.logger = logging.getLogger('')

        # if self.instance:
        #     raise RuntimeError('An instance of %s plugin already exists' % type(self).__name__)
        type(self).instance = self

    def options(self, parser, env):
        """Register commandline options and grab all options after --xargs to
        pass on to the test suites.
        """
        def gobble_all_remaining_args(option, opt_str, value, parser):
            self.logger.debug('Capturing xargs arguments:%r' % (parser.rargs))
            xargs = []
            while parser.rargs:  # Steal all following args
                xargs.append(parser.rargs.pop(0))
            type(self).xargs = xargs

        def split_args(option, opt_str, value, parser):
            self.logger.debug('Splitting arguments:%s' % (value))
            args = value.replace(',', ' ').split()
            while parser.rargs and not parser.rargs[0].startswith('-'):  # Steal all following args until '-'
                args.append(parser.rargs.pop(0))
            setattr(parser.values, option.dest, args)

        parser.add_option(
            "--xreport-file", "--xfile",
            action="store",
            dest='xreport_file',
            # default=env.get('NOSE_XREPORT_FILE', './test'),
            default=None,
            help='Report output path and base filename, without extension. The output files will be appended by .xml, .rst and _attachment_id.png')
        parser.add_option(
            "--xformat",
            action="callback",
            callback=split_args,
            type='string',
            dest='xformat',
            default=['pdf'],
            help='Output format in addition to the xml file: pdf or rst')
        # parser.add_option(
        #     '--xquiet',
        #     action="store_true",
        #     dest="xquiet",
        #     default=False)
        parser.add_option( # This must be the last option since it gobbles everything else...
            "--xargs",
            action="callback",
            callback=gobble_all_remaining_args,
            help='Any arguments that follow will be grabbed and made accessible to the tests as the `xargs` attribute of the xreport module.')

    def configure(self, options, conf):
        """Configure plugin. Plugin is enabled by default.
        """
        super(XReport, self).configure(options, conf)
        self.conf = conf  # debug
        self.options = options
        self.enabled = True  # Plugin is enabled by default
        self.logger.debug('Config is %s' % conf)
        self.filename = options.xreport_file
        self.formats = set(options.xformat)
        self.verbose = options.verbosity
        self.filename, filename_ext = os.path.splitext(self.filename)
        # if not self.formats:
        #     self.formats = []
        if filename_ext[1:]:
            self.formats.add(filename_ext[1:])
        for f in self.formats:
            if f not in ('pdf', 'rst', 'xml'):
                raise ValueError("Invalid file format type '%s'" % f)

        # self.conf = conf
        # if not options.capture:
        #     self.enabled = False

    def setOutputStream(self, stream):
        """Intercept output stream configuration and forward to a dummy device."""
        # return dummy stream
        class DummyIO:
            def write(self, *arg):
                pass
            def writeln(self, *arg):
                pass
            def flush(self):
                pass
        # If we are verbose, send all text to screen, else send to dummy device
        if self.verbose:
            self.stream = stream
        else:
            self.stream = DummyIO()


        return DummyIO()

    def start_stdout_capture(self):
        """ Redirect Stdout in a StringIO"""
        self.stdout.append(sys.stdout)
        self._buf = StringIO()
        sys.stdout = self._buf

    def stop_stdout_capture(self):
        """ Restore the original stdout device"""
        buf = self._buf.getvalue()
        if self.stdout:
            sys.stdout = self.stdout.pop()
        return buf

    def flush_stdout_capture(self):
        """Get currently captured output and flush buffer"""
        buf = self._buf.getvalue()
        self._buf.truncate(0)
        return buf

    def get_current_node(self):
        """ Return the current XML node """
        return self.node_tail[-1]

    def add_node(self, *data):
        """ Add one or more children XML elements to the current node"""
        self.get_current_node().extend(data)

    def enter_node(self, node=GROUP(), node_name='.'):
        """ Create a new XML children node and make it current"""
        self.add_node(node)
        self.node_tail.append(node)  # make new node current
        self.node_name.append(node_name)

    def exit_node(self):
        """ Terminate a node and make parent node current"""
        self.node_tail.pop()
        self.node_name.pop()  # flush the current node name

    def get_node_path(self):
        """ Return the full hierarchical name of the current node"""
        return '.'.join(self.node_name)

    def _insert_plot(self, caption='', format='png'):
        """ Insert a matplotlib plot in the test report"""
        # insert whatever captured text we have so far
        captured_output = self.flush_stdout_capture()
        if captured_output:
            self.add_node(DETAILS(PRE(captured_output)))

        # Grab and convert image to URI
        io = StringIO()
        plt.gcf().savefig(io, format=format)
        self.last_image = io.getvalue()

        uri = ('data:image/%s;base64,' % format +
               urllib.quote(base64.b64encode(io.getvalue())))
        # insert image
        self.add_node(FIGURE(IMG(src=uri), FIGCAPTION(caption), style='text-align:center'))

    def _output(self, message):
        """ Prints an interactive message to the user """
        self.original_stdout.write(message + '\n')
        self.original_stdout.flush()

    def _flush(self):
        """ Flush the current standard output and start a new block of text."""
        captured_output = self.flush_stdout_capture()
        if captured_output:
            self.add_node(DETAILS(PRE(captured_output)))  # Add any stdout capture
            self.stream.write(captured_output)

    def pprint(self, text, dedent=True):
        """ Add a block of text verbatim to be interpreted a reStructuredText"""
        self.flush()
        if dedent:
            text = textwrap.dedent(text)
        self.add_node(DETAILS(P(text)))
        self.stream.write(text)

    def begin(self):
        """Initialize the test run.
        """
        self.logger.info('begin')

        # xreport_modules = [module_name for module_name in sys.modules.keys() if 'xreport' in module_name]
        # if len(xreport_modules)!=1:
        #     raise RuntimeError('There are multiple versions of this module loaded in memory. those are: %s' % xreport_modules)

        # global xargs, insert_plot, output, flush, rst, rst_on, rst_off
        # xargs = self.xargs  # Pass command line arguments to test instance
        # insert_plot = self.insert_plot
        # output = self.output
        # flush = self.flush
        # rst = self.pprint

        self.logger.info('begin - setting xargs= %s on xreport module ID %s ' % (self.xargs, type(self).__module__))

        self.start_stdout_capture()  # get an early handle on sys.stdout
        test_date = datetime.datetime.now().isoformat()
        self.add_node(CONTEXT_TABLE({
            'Run start date/time': test_date,
            'Xargs': self.xargs,
            'Command line arguments': sys.argv,
            'Target file name': '(undefined)',
            }))
        self.add_node(TESTNAME(sys.argv[0]))
        self.add_node(TITLE('Test Run'))
        self.add_node(TESTNAME('(test run)'))
        self.add_node(TESTPATH('(test run)'))
        self.add_node(TESTARGS())
        self.add_node(TESTDATE(test_date))

        self.stream.write('Test Run (%s)\n\n' % test_date)

    def startContext(self, ctx):
        self.last_context = ctx  # for debug
        self.logger.info('StartContext %s' % ctx)
        try:
            group_name = ctx.__name__
        except AttributeError:
            group_name = str(ctx)

        # If this is a module, get the path
        try:
            path = ctx.__file__.replace('.pyc', '.py')
        except AttributeError:
            path = '...unknown...'

        title, description = self._get_doc(ctx)
        context_type = ('MODULE' if inspect.ismodule(ctx) else
                        'GENERATOR' if inspect.isgeneratorfunction(ctx) else
                        'CLASS' if inspect.isclass(ctx) else '')
        full_title = context_type + ' ' + self.get_node_path()
        test_datetime = datetime.datetime.now().isoformat()
        self.enter_node(GROUP(), group_name)
        self.add_node(TESTNAME(self.get_node_path()))
        self.add_node(TITLE(full_title))
        self.add_node(TESTPATH(self.get_node_path()))
        self.add_node(TESTDATE(test_datetime))
        self.add_node(TESTARGS())
        self.add_node(DESCRIPTION(B(title), DETAILS(description)))

        self.stream.write('%s (%s)\n\n' % (full_title, test_datetime))

        self.logger.info('StartContext %s completed' % ctx)

    def all_nodes_passed(self):
        """ gather the pass/fail node of every underlying test case or group"""
        return all([n.passed.text == 'true' for n in self.get_current_node().iterchildren(['case', 'group'])])

    def stopContext(self, ctx):
        self.logger.info('StopContext %s, etree=%s' % (ctx, self.etree))
        self.add_node(PASSED(self.all_nodes_passed()))
        self.exit_node()
        self.logger.info('StopContext %s Completed' % (ctx))

    def beforeTest(self, test):
        """Flush capture buffer.
        """
        self.logger.info('beforeTest %s' % test)
        self.start_stdout_capture()

    def startTest(self, test):
        self.last_test = test  # debug

        if isinstance(test.test, nose.case.FunctionTestCase):
            test_type = 'FUNCTION'
            test_name = test.test.test.func_name
            summary, description = self._get_doc(test.test.test)
        elif hasattr(test.test, '_testMethodName'):
            test_type = 'METHOD'
            test_name = test.test._testMethodName
            summary, description = self._get_doc(test.test._testMethodDoc)
        else:
            test_type = str(type(test.test))
            test_name = type(test.test).__name__
            summary, description = self._get_doc(test.test)  # ? Not sure yet what to do here if this ever happens
        test_args = str(getattr(test.test, 'arg', "()")).replace(',)', ')')

        self.enter_node(CASE(), test_name)  # Begin new node. Must be before we use get_node_path()

        title = '%s %s%s' % (test_type, self.get_node_path(), test_args)
        self.logger.info('startTest %s' % test_name)
        test_date = datetime.datetime.now().isoformat()
        self.add_node(TITLE(title))
        self.add_node(TESTNAME(test_name))
        self.add_node(TESTPATH(self.get_node_path()))
        self.add_node(TESTDATE(test_date))
        self.add_node(TESTARGS(test_args))
        self.add_node(DESCRIPTION(B(summary), DETAILS(description)))

        self.stream.write('%s (%s)\n\n' % (title, test_date))


    def stopTest(self, test):
        self.logger.info('stopTest %s ' % test)

    def afterTest(self, test):
        """Clear capture buffer.
        """
        self.logger.info('afterTest %s' % test)
        self.flush()
        self.stop_stdout_capture()
        self.exit_node()

    def addSuccess(self, test):
        self.logger.info('addSuccess %s' % test)
        self.add_node(PASSED(True))

    def addError(self, test, err):
        summary = err[1][:err[1].find('\n--------')].replace('\n',' ')  # Strip captured stdout or logs from summary text
        self.add_node(SUMMARY(summary))
        err = self.formatErr(err)
        self.logger.info('addError %s' % (err[-1000:]))
        self.flush()
        self.add_node(DETAILS(PRE(err)))  #
        self.add_node(PASSED(False))
        self.stream.write('\n%s\n' % (err))

    def addFailure(self, test, err):
        summary = err[1][:err[1].find('\n--------')].replace('\n',' ')
        self.add_node(SUMMARY(summary))
        err = self.formatErr(err)
        self.logger.info('addFailure %s' % (err[-1000:]))
        self.flush()
        self.add_node(DETAILS(PRE(err)))  #
        self.add_node(PASSED(False))
        self.stream.write('\n%s\n' % (err))

    def formatFailure(self, test, err):
        """Add captured output to failure report.
        """
        return self.formatError(test, err)

    def formatErr(self, err):
        exctype, value, tb = err
        return ''.join(traceback.format_exception(exctype, value, tb))

    def formatError(self, test, err):
        """Add captured output to error report.
        """
        ec, ev, tb = err
        return (ec, str(ev), tb)

    def finalize(self, result):
        """
        """
        self.logger.info('Finalize')
        # Restore stdout.
        while self.stdout:
            self.stop_stdout_capture()

        self.add_node(PASSED(self.all_nodes_passed()))

        number_of_tests = result.testsRun

        self.stream.write('-----------------------------------------\n')

        if not result.wasSuccessful():
            self.add_node(DETAILS(PRE('Ran %d tests: FAILED (failures=%d, errors=%d)' % (number_of_tests, len(result.failures),len(result.errors)))))
        else:
            self.add_node(DETAILS(PRE('Ran %d tests: SUCCESS' % number_of_tests)))

        synopsis = '\n'.join(self.get_synopsis_as_strings())
        self.add_node(DETAILS(PRE(synopsis)))
        self.stream.write('%s\n' % synopsis)

        sys.stdout = self.original_stdout

        if self.filename:
            self.write_xml()
            self.write_rst()
            self.write_pdf()

    @staticmethod
    def _get_doc(thing):
        '''Try to convert DocStrings into a (title, description) tuple.'''

        # Grab information from DocStrings
        if isinstance(thing, str):
            doc = thing
        else:
            doc = inspect.getdoc(thing) or 'No doctring'
        title = doc.splitlines()[0]
        description = '\n'.join(doc.splitlines()[1:])

        # # Markup to HTML
        # title = docutils.core.publish_parts(title, writer_name='html')['body']
        # description = docutils.core.publish_parts(description, writer_name='html')['body']

        # # Markupify and parse into XHTML
        # title = lxml.html.fromstring(title)
        # description = lxml.html.fragments_fromstring(description)

        return (title, description)

    def print_etree(self, node=None, level=0):
        if node is None:
            node = self.etree

        for e in node:
            if e.text:
                text = str(e.text).replace('\n',' ')
                if len(text) > 64:
                    text = text[:64] + '...'
            else:
                text = ''
            print '%s%s = %s' % ('   '*level, e.tag.upper(), text)
            self.print_etree(e.getchildren(), level+1)

    def get_synopsis(self):
        etree = self.etree
        return [(str(getattr(x, 'testdate', '?')),
                 str(getattr(x, 'testpath', '?')),
                 str(getattr(x, 'passed', '?')),
                 str(getattr(x, 'summary', '')))
                for x in etree.iter(['case', 'group'])]

    def get_synopsis_as_strings(self):
        syn = self.get_synopsis()
        col_width = [0, 0, 0, 0]
        for item in syn:
            for (i, field) in enumerate(item):
                    col_width[i] = max(col_width[i], len(str(field)))
        format_ = '| ' + ' | '.join('%%-%is' % width for width in col_width) + ' |'

        return [format_ % item for item in syn]

    def print_synopsis(self):
        print self.get_synopsis_as_strings()

    def get_xml(self, xslt='xreport.xsl'):
        '''Export as XML, with embedded XSL stylesheet so the browser can show the formatted data'''
        if self.etree is None:
            raise RuntimeError('The test has not been run yet')

        # get the XSL style sheet
        stylesheet = os.sep.join(__file__.split(os.sep)[:-1]+[xslt])

        xsl = lxml.etree.parse(open(stylesheet))

        # Create an empty XML document
        xml = lxml.etree.XML(
            '<?xml version="1.0" encoding="UTF-8"?> \n'
            '<!DOCTYPE root [<!ATTLIST xsl:stylesheet id ID  #REQUIRED>]> \n'
            '<?xml-stylesheet type="text/xsl" href="#xslt"?>\n'
            '<root></root>\n')
        xml = lxml.etree.ElementTree(xml)
        root = xml.getroot()  # Get the root object of the empty document
        root.append(xsl.getroot())  # Add the XSL stylesheet to root

        # Add the data to root
        root.append(deepcopy(self.etree)) #use deepcopy because this seems to change the original object

        return lxml.etree.tostring(xml, pretty_print=True)

    def write_xml(self, filename=None):
        filename = filename or self.filename
        with open(filename+'.xml', 'w') as f:
            f.write(self.get_xml())

    def get_rst(self, filename=None):
        """ Return the object representating the test report in reStructuredTest with attachments."""
        filename = filename or self.filename

        rst = rST(filename)
        rst.add_toc(depth=5)
        self._get_rst_from_group_node(rst, self.etree)
        return rst

    def write_rst(self, filename=None):
        filename = filename or self.filename
        rst = self.get_rst(filename)
        rst.write()

    def write_pdf(self, filename=None):
        """ Write the report as a PDF file.

        Latex is not needed. The rst2pdf package (pip install rst2pdf) is required.
        """
        filename = filename or self.filename

        from reportlab.platypus import flowables
        from rst2pdf import createpdf

        # Set listWrapOnFakeWidth to False to make sure the wrap() command
        # report the actual width of (literal) boxes, not the available width.
        # This way the boxes can scale correctly to fit the width of the page.

        # Note that reportlab's flowables module loads listWrapOnFakeWidth
        # from the rl_config module with an import statement at module load
        # time. Changing the rl_config value after that has no effect. For
        # this reason, we change it firectly in the flowables module.
        flowables.listWrapOnFakeWidth = 0

        r = createpdf.RstToPdf(stylesheets=['eightpoint', 'letter', 'sphinx'], fit_mode='shrink', breaklevel=0)
        r.createPdf(text=str(self.get_rst()), output=filename + '.pdf')

    def publish(self, filename, writer_name='html'):
        """ Write the report in any of the formats supported by the ``docutils`` library.
        """
        filename = filename or self.filename
        rst = self.get_rst(filename)
        rst.write(writer_name=writer_name)

    def _get_rst_from_group_node(self, rst, node, level=0):
        rst.add_section(str(node.title), level)
        # First include the contents of the 'description' (from docstrings).
        # We assume this is always in reStructuredtext format
        for n in node.iterchildren('description'):
            rst.add('\n'.join(n.itertext()))
            rst.add('\n')
        # Insert summary here

        # Now process the test outputs: details and figures, in the order they
        # are stored in the test data structure
        for n in node.iterchildren('details', 'figure'):
            if n.tag == 'figure':
                image = self._get_binary_from_img_node(n.img)
                caption = n.figcaption.text
                rst.add_binary_image(image, caption=caption)
            if n.tag == 'details':
                for nn in n.iterdescendants():
                    self.logger.debug('Processing node %s.%s' % (n.tag, nn.tag))
                    if nn.tag == 'pre':
                        rst.add_literal_block('\n'.join(nn.itertext()))
                    else:
                        rst.add(nn.text + '\n')
            rst.add('\n')
        for n in node.iterchildren('group', 'case'):
            self._get_rst_from_group_node(rst, n, level+1)

    def _get_binary_from_img_node(self, node):
            target ='base64,'
            src = node.attrib['src']
            start_index = src.find(target) + len(target)
            binary = base64.b64decode(urllib.unquote(src[start_index:]))
            return binary

    @classmethod
    def run_from_module(cls):
        """ Run the nose tests with the XReport plugin loaded and activated on the currently executed module.
        """
        import logging.handlers
        log_handler = logging.handlers.SysLogHandler()
        logger = logging.getLogger('')
        logger.handlers = []  # Clear all existing handlers
        logger.setLevel(logging.DEBUG)
        logger.addHandler(log_handler)

        x = cls()  # Plugin is enabled by default. No need to use the option --with-xreport
        argv = sys.argv
        module_name, __ = os.path.splitext(argv[0])  # remove .py extension from module name
        # if not argv[1].startswith(
        nose.run(argv=[argv[0], module_name] + argv[1:], addplugins=[x])
        return x


class rST():
    """
    Allows the creation of very simple ReStructuredText
    documents.

    Based on reStructuredText.py developed by Kevin MacDermid, August 2014
    """
    def __init__(self, base_filename=None):
        """
        Creates a new reStructuredText document.
        """
        if base_filename is None:
            self.base_filename = datetime.datetime.now().strftime('%Y-%m-%d_%Hh%Mm%Ss')
        else:
            self.base_filename = base_filename
        self.rst = StringIO()
        self.attachments = {}  # {tag:data, ...}

    def __str__(self):
        return self.rst.getvalue()

    def __iadd__(self, string):
        self.add(string)
        return self

    def write(self, writer_name=None):
        if writer_name is not None:
            doc = docutils.core.publish_string(self.rst.getvalue(), writer_name=writer_name)
        else:
            doc = self.rst.getvalue()

        with open(self.base_filename + '.rst', 'w') as f:
            f.write(doc)
        for (tag, data) in self.attachments.items():
            attachment_filename = self.base_filename + '_' + tag
            with open(attachment_filename, 'wb') as f:
                f.write(data)

    def add(self, string):
        self.rst.write(string)

    def add_all(self, string_list):
        for string in string_list:
            self.rst.write(string)

    def add_attachment(self, filename, data):
        self.attachments[filename] = data

    def add_toc(self, depth=2, toc_title='**Local Table of Contents**', local=False):
        self.add('\n')
        self.add('.. class:: center\n')
        self.add('\n')
        self.add('%s\n' % toc_title)
        self.add('\n')
        self.add('.. contents::\n')
        if local:
            self.add('    :local:\n')
        self.add('    :depth: %i\n' % depth)

    def add_section(self, text, level):
        adornment = ('==', '--', '=', '-', '~', '^', '.' )[level]
        self.add('\n\n')
        if len(adornment) > 1:
            self.add('%s\n' % (adornment[0] * len(text)))
        self.add('%s\n' % (text))
        self.add('%s\n' % (adornment[0] * len(text)))

    def add_binary_image(self, image, format='png', tag=None, caption=None):
        if tag is None:
            tag = 'image%i' % len(self.attachments)
        tag = tag + '.' + format
        self.add_attachment(tag, image)
        image_uri = self.base_filename + '_' + tag
        self.add_image(image_uri, caption=caption)

    def add_image(self, image_path, height=None, width=None, align='center', caption=None):
        '''
        Adds an immage to the reStruturedText document specified at instantiation

        Args:
            image_path: The absolute path to the image
            height: (optional) The height of the image. String including units. e.g. '100 px'
            width: (optional) The width of the image. String including units. e.g. '100 px'
            align: (optional) The alignment of the image. e.g. 'left', 'right', 'center' (default)
        '''
        self.add('\n')
        self.add(".. figure:: %s \n" % (image_path))
        if height is not None:
            self.add("   :height: %s\n" % (height))
        if width is not None:
            self.add("   :width: %s\n" % (width))
        self.add("   :align: %s\n" % (align))
        self.add('\n')
        if caption:
            for line in caption.split('\n'):
                self.add('   ' + line + '\n')
            self.add('\n')

    def add_literal_block(self, text):
        self.add('\n')
        self.add('::\n')
        self.add('\n')
        for line in text.split('\n'):
            self.add('    ' + line + '\n')
        self.add('\n')

    def add_table(self, grid, header=False):
        '''
        Writes a table from elements in grid.
        Shamelessly stolen from:
            http://stackoverflow.com/questions/11347505/what-are-some-approaches-to-outputting-a-python-data-structure-to-restructuredte
        Args:
            grid: A list of tuples containing the table elements.
                Must be square and first line is the table header.
            header: A flag to make the first row a header row
        Output:
            Writes the table to the the given restructured text file.
        '''

        nonzero_grid = []
        single_elements = []
        for row in grid:
            if len(row) > 1:
                nonzero_grid.append(row)
            else:
                single_elements.append(str(row[0]))
        num_cols   = len(nonzero_grid[-1])
        body_cell_width = 2 + max(reduce(lambda x,y: x+y, [[len(str(item)) for item in row] for row in nonzero_grid], []))
        if single_elements:
            biggest_single_width = len(max(single_elements))
            if num_cols * body_cell_width > biggest_single_width:
                cell_width = body_cell_width
            else:
                cell_width = biggest_single_width
        else:
            cell_width = body_cell_width
        rst = self._table_div(num_cols, cell_width, 0)
        total_cell_width = num_cols*cell_width

        #A table with one row is malformed if it has a header
        if len(grid) > 1:
            header_flag = header
        else:
            header_flag = False
        for i, row in enumerate(grid):
            if isinstance(header, int):
                if i==header-1:
                    header_flag = True
                else:
                    header_flag = False
            if len(row) > 1:
                use_cw = (total_cell_width/len(row)) - 1
            else:
                use_cw = (total_cell_width/len(row)) + num_cols-2  ## Since the "|"s also produce an offset
            rst += '| ' + '| '.join([self._normalize_cell(str(x), use_cw) for x in row]) + '|\n'
            rst += self._table_div(num_cols, cell_width, header_flag)
            header_flag = False
        rst += '\n'
        self.add(rst)

    def _table_div(self, num_cols, col_width, header_flag):
        '''
        A table writing helper function, see write_table.
        '''
        if header_flag:
            return num_cols*('+' + (col_width)*'=') + '+\n'
        else:
            return num_cols*('+' + (col_width)*'-') + '+\n'

    def _normalize_cell(self, string, length):
        '''
        A table writing helper function, see write_table.
        '''
        return string + ((length - len(string)) * ' ')


def main():
    """ Run the nose tests with the XReport plugin loaded and activated, and
    save the XML and RST reports using the specified ``filename`` prefix.
    """
    import logging.handlers
    log_handler = logging.handlers.SysLogHandler()
    logger = logging.getLogger('')
    logger.handlers = []  # Clear all existing handlers
    logger.setLevel(logging.DEBUG)
    logger.addHandler(log_handler)

    import xreport as xr
    xr.XReport.instance = None  # (debug) Bypass check to allow creation of a new instance of the plugin
    x = xr.XReport()  # Plugin is enabled by default. No need to use the option --with-xreport
    nose.run(addplugins=[x])
    return x

if __name__ == '__main__':
    x = main()
