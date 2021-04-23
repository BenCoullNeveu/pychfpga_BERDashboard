import datetime
from py.xml import html
from py.xml import raw
import pytest
import re
import os

from matplotlib import pyplot as plt

from wtl.namespace import NameSpace
from pytest_html import extras

def pytest_html_results_table_html(report, data):
    """ Move HTML images after their mention as .. image:: or .. figre:: in the logged output.
    """
    print(f' Report data = {data}')
    log = None
    for d in data:
        print(f'Processing {d.attr.class_}')
        d.attr.style = "float:none;"
        if d.attr.class_== 'image':
            pass
        elif d.attr.class_ == "log":
            log = d
    if not log:
        return

    logitems = log[:]
    log.clear()
    # move captured output to the top of the cell
    data.remove(log)
    data.insert(0, log)
    data.insert(1, " Unreferenced resources ".center(80,'-') + '\n')
    # don't limit height of capture cell
    log.attr.style = "height:unset;"
    # look for ..image:: or .. figure::. If found, move corresponding
    # node just before it
    for t in logitems:
        if isinstance(t, raw):
            for s in t.uniobj.splitlines(keepends=True):
                g = re.match(r"\.\. (image|figure)::\s*(\S*)", s)
                if g:
                    url = g.group(2)
                    for im in data:
                        if hasattr(im,'attr') and im.attr.class_== 'image' and im[0].attr.href == url:
                            print(f'Adding {im}')
                            data.remove(im)
                            log.append(im)
                            break
                log.append(raw(s))
        else:
            log.append(t)
            print(f'added {type(t)} = {t!r}')

@pytest.fixture
def xr(extra, request):
    return XReport(extra, request)


class XReport:
    """ A ``pytest`` plugin to implement interactive and incremental testing of hardware
    """
    def __init__(self, extra, request):
        """
        Parameters:

            extra (Fixture): a pytest-html fixture
        """

        self.extra = extra
        self.request = request
        self.params = NameSpace()
        self.attachments = {}
        self.figure_number = 0
        self.xml_pathname = request.config.option.xmlpath
        if not self.xml_pathname:
            raise RuntimeError('A xml output path mush be specified with the command line option --junit-xml=<filename>')
        self.xml_folder, self.xml_filename = os.path.split(self.xml_pathname)
        print(f'fixturename={self.request.fixturename}')
        print(f'node={self.request.node}')
        print(f'listchain={self.request.node.listchain()}')
        print(f'function={self.request.function}')
        print(f'fspath={self.request.fspath}')
        print(f'nodeid={self.request.node.nodeid}')
        # self.test_folder = os.path.dirname(self.xmlpath)
        self.nodeid = self.request.node.nodeid
        self.short_nodeid = os.path.split(self.nodeid)[1].replace('.py','')
        xml_basename, _ = os.path.splitext(self.xml_filename)
        self.asset_folder = os.path.join(self.xml_folder, f'{xml_basename}_assets')
        self.asset_basename = self.short_nodeid.replace('::',".")
        os.makedirs(self.asset_folder,  exist_ok=True)
        print(f'short_nodeid={self.short_nodeid}')
        print(f'asset_folder={self.asset_folder}')
        print(f'asset_basename={self.asset_basename}')

    def add_image(self, url):
        self.extra.append(extras.image(url))
        print(f'.. image:: {url}')
        print(f'  :width: 80%')
        print(f'  :align: center')

    def add_figure(self, url, caption):
        self.extra.append(extras.image(url))
        print(f'.. figure:: {url}')
        print(f'  :width: 80%')
        print(f'  :align: center')
        print()
        if caption:
            for line in caption.splitlines():
                print(f'  {line}')

    def header(self, title):
        print(title)
        print('='*len(title))
        print()

    def input(self, message):
        answer = input(message)
        # Send a copy of the message and answer to the capture buffer because
        # raw_input bypasses stdout for some reason.
        # print(str(message)+answer+'\n')
        return answer


    @classmethod
    def generate_test_summary(self, *args, **kwargs):
        return generate_test_summary(*args, **kwargs)

    @classmethod
    def generate_combined_summary(self, *args, **kwargs):
        return generate_combined_summary(*args, **kwargs)

    def insert_plot(self, caption=""):
        # Grab and convert image to URI
        # io = StringIO()
        # image = io.getvalue()
        self.figure_number += 1
        asset_filename = f'{self.asset_basename}_Figure{self.figure_number}.png'
        asset_pathname = os.path.join(self.asset_folder, asset_filename)
        # self.assets[asset_pathname] = image
        self.add_figure(asset_pathname, caption=f'Figure {self.figure_number}: {caption}')
        plt.gcf().savefig(asset_pathname, format='png')
        # uri = ('data:image/%s;base64,' % format +
        #        urllib.parse.quote(base64.b64encode(io.getvalue())))
        # insert image
        # self.add_node(FIGURE(IMG(src=uri), FIGCAPTION(caption), style='text-align:center'))

    def pass_fail(cls, test):
        return ['FAIL','PASS'][bool(test)]

    def save_data(self, data):
        self.rep.add_data(data)

import glob
import logging
import lxml.etree
import lxml.objectify
import base64
import urllib

# import lxml.html
from wtl.xreport.rst import rST

def _xreport_to_junit_(node, asset_folder_path='assets'):
    """ Convert a legacy xreport xml node into a junit-compatible xml node.

    The following transformations are done:

     - headers are conterted to restructured text representation
     - <images> are replaced with a ``.. image::`` rst block, and image is added to the `assets` dict.

    Parameters:

        node (lxml.objectify.Element): <case> xml element

        asset_folder_path (str): path to the assets folder. Is used only to
            create the .. image:: directive arguments and asset keys. Images
            are not saved.

    Returns:

        A (nodeid, testdate, passed, node, assets) tuple where:

            nodeid (str): hierarchical name of the test (a.k.a. testpath)

            testdate (str): Date of the test

            passed (bool): Indicates whether the test passed or not

            node (lxml.etree.Element): <testcase> xml element

            assets (dict): {filename:binaty_image, ...} dictionary contains the binary blobs of embedded images

    """
    # filename = filename or self.filename
    # filename, filename_ext = os.path.splitext(filename)

    rst = rST()
    # rst.add_toc(depth=5)
    passed = True
    testname = None
    testpath = None
    testdate = None
    assets = {}
    figure_number = 1
    def _node_to_rst(node, level=0):
        # allow assignment to the following variable without creating a local one
        nonlocal passed, testname, testpath, testdate, figure_number
        rst.add_section(str(node.title), level)
        # First include the contents of the 'description' (from docstrings).
        # We assume this is always in reStructuredtext format
        for n in node.iterchildren('description'):
            rst.add('\n'.join(n.itertext()))
            rst.add('\n')
        # Insert summary here

        # Now process the test outputs: details and figures, in the order they
        # are stored in the test data structure
        for n in node.iterchildren():
            # print(f'{n.tag}: {n.text}')
            if n.tag == 'testname':
                testname = n.text
            elif n.tag == 'testpath':
                testpath = n.text
            elif n.tag == 'testdate':
                testdate = n.text
            if n.tag == 'header':
                # self.logger.debug('Got a header on node %s' % (n.tag))
                rst.add_section(str(n), level+1)
            elif n.tag == 'passed':
                passed = n.text.lower() == "true"
            elif n.tag == 'figure':
                caption = n.figcaption.text
                # data URL is in the format data:[<mediatype>][;base64],<data>
                # We expect data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAoAAAAHgCAYAAAA10dzkAA...
                data_url = n.img.get('src')
                target ='base64,'
                start_index = data_url.find(target) + len(target)
                image = base64.b64decode(urllib.parse.unquote(data_url[start_index:]))
                normalized_testname = testpath
                figure_filename = f'{normalized_testname}_Figure{figure_number}'
                figure_pathname = os.path.join(asset_folder_path, figure_filename)
                print(f'Extracting {figure_pathname}')
                rst.add_image(figure_pathname, caption=caption)
                figure_number += 1
                assets[figure_pathname] = image
            elif n.tag == 'data':
                # print('Data block is ignored')
                pass
            elif n.tag == 'details':
                for nn in n.iterdescendants():
                    # self.logger.debug('Processing node %s.%s' % (n.tag, nn.tag))
                    if nn.tag == 'pre':
                        # rst.add_literal_block('\n'.join(nn.itertext()))
                        rst.add('\n'.join(nn.itertext()))
                    else:
                        rst.add(nn.text + '\n')
            rst.add('\n')
            print(f'testpath={testpath}')

        for n in node.iterchildren('group', 'case'):
            _node_to_rst(n, level+1)

    _node_to_rst(node)

    # repackage into a junit testcase
    classname, name = testpath.rsplit('.', 1)
    testcase = lxml.etree.Element('testcase', classname=classname, name=name, time="0.0")
    system_out = lxml.etree.SubElement(testcase, 'system-out')
    system_out.text = str(rst)
    if not passed:
        failure = lxml.etree.SubElement(testcase, 'failure')
        failure.text = 'Test has not passed'

    return testpath, testdate, passed, testcase, assets

class TestCase:
    def __init__(self, nodeid, filename=None, date="", passed=False, node=None, assets={}, name=None):
        self.filename = filename
        self.nodeid = nodeid
        self.date = date
        self.passed = passed
        self.node = node
        self.assets = assets
        self.dotted_nodeid = nodeid.replace('::', '.').replace(':', '.')
        self.name = name or self.dotted_nodeid.rsplit('.', 1)[-1]
        self.status_message = "Passed" if self.passed else ""

def load_test_cases(input_folder='.'):
    """ Return a dictionary of test cases found in all the the files in the folder specified by ``input_folder``.

    Returns:
        dict {nodeid:[TestCase, ...], ...}


    Each entry is {test_name : [TestCase, ...]}. The list elements are sorted by most recent test first.
    """
    logger = logging.getLogger('')
    glob_pattern = input_folder + '/*.xml'
    filenames = glob.glob(glob_pattern)
    print(f'Loading xml files {glob_pattern}')


    # Load data from all files, whether they are old xreport or junit XML files
    file_data = {}
    for filename in filenames:
        print(f'Loading: {filename}')
        with open(filename) as file_:
            etree = lxml.objectify.parse(file_)  # use objectify (instead of etree) to allow attribute-wise access to elements
        file_data[filename] = etree
    # print(f'files = {file_data}')

    # build a dictionary of all test cases
    test_cases = {}
    for fn, group in file_data.items():
        # Find xreport test cases for legacy support
        pathname, ext = os.path.splitext(fn)
        asset_folder_path = f'{pathname}_assets'
        # print(f'asset folder = {asset_folder_path} (fn={fn}, pathname={pathname}')
        for xreport_case in group.iter('case'):  # find all test case objects, wherever they are in the hierarchy
            nodeid, testdate, passed, node, assets = _xreport_to_junit_(xreport_case, asset_folder_path=asset_folder_path)
            test_cases.setdefault(nodeid, []).append(TestCase(
                filename=fn,
                nodeid=nodeid,
                date=testdate,
                passed=passed,
                node=node,
                assets=assets))
            print(f'xreport assets = assets')
        # Find junit test cases
        for suite in group.iter('testsuite'):  # find all testsuites
            testdate = suite.get('timestamp')
            for testcase in suite.iter('testcase'):  # find all test testcase objects, wherever they are in the hierarchy
                nodeid = f"{testcase.get('classname')}.{testcase.get('name')}"
                rst = rST()
                for n in testcase.iterchildren('system-out', 'system-err'):
                    rst.add_literal_block(n.text)
                passed = not list(testcase.iterchildren('failure', 'error'))
                test_cases.setdefault(nodeid, []).append(TestCase(
                    filename=fn,
                    nodeid=nodeid,
                    date=testdate,
                    passed=passed,
                    node=testcase))

    # sort the cases by date
    for nodeid, tcs in test_cases.items():
        tcs.sort(key=lambda c: c.date, reverse=True)  # sort by reverse date
    return test_cases

def get_test_status(test_cases, required_tests):
    """
    Return a list containing the TestCase object for all specified
    required tests, with missing tests filled in as failed tests.

    Parameters:

        test_cases (list): List of all tests that have been conducted so far,
            as returned by `load_test_cases`.

        required_tests (list): is a list of test_names. Semicolons separators
            are replaced by '.'.

    Returns:
        List of NameSpace containing the following elements

            - filename: filename of the file containing the test result
            - path: full test ID
            - name: last element of test ID
            - date: date of the test
            - passed: True if the test passed
            - message: additional info on test status
    """
    # Make sure we use a standard 'dot' notation for the test id...
    # required_tests = [t.replace('::', '.').replace(':', '.') for t in required_tests]

    test_cases = []
    for nodeid in required_tests:
        if nodeid in test_cases:
            testcase = test_cases[nodeid][0]  # get the most recent test
        else:
            testcase = TestCase(nodeid = nodeid)
            testcase.status_message = 'Test not run'
        test_cases.append(testcase)
    return test_cases

def generate_aggregate_junit(input_folder, output_pathname='summary.xml'):
    """
    Create an aggregate junit testsuite.

    The report is a <testsuites> node, containing one <testsuite> per date.
    Each <testsuite> contains the <testcase> obtained on the same run.
    """

    output_folder = os.path.dirname(output_pathname)

    test_cases = load_test_cases(input_folder=input_folder)

    # extract most recent testcase for each nodeid
    test_cases = {nid:tcs[0] for nid, tcs in test_cases.items()}

    print(f'testcases={test_cases}')
    testsuites = lxml.etree.Element('testsuites')
    test_dates = {tc.date for tc in test_cases.values()}
    for td in test_dates:
        tcs = [tc for tc in test_cases.values() if tc.date == td]
        passed = sum(bool(tc.passed) for tc in tcs)
        testsuite = lxml.etree.SubElement(
            testsuites,
            'testsuite',
            name="pytest",
            errors="0",
            failures=str(len(tcs) - passed),
            skipped="0",
            tests=str(len(tcs)),
            time="0.0",
            timestamp=td,
            hostname="unknown")
        for tc in tcs:
            testsuite.append(tc.node)
            # save image assets
            for pathname, image in tc.assets.items():
                os.makedirs(os.path.dirname(pathname), exist_ok=True)
                with open(pathname, 'wb') as f:
                    f.write(image)

    # Update image link paths
    for n in testsuites.iter('system-out', 'system-err'):
        new_text = []
        for line in n.text.splitlines():
            g = re.match(r"\.\. (image|figure)::\s*(\S*)", n.text)
            if g:
                directive = g.group(1)
                old_pathname = g.group(2)
                old_path, filename = os.path.split(old_pathname)
                new_path = os.path.relpath(output_folder, old_path)
                new_pathname = os.path.join(new_path, filename)
                line = f'.. {directive}:: {new_path}'
                print(f'Line modified to: {line}')
            new_text.append(line)
        n.text = '\n'.join(new_text)


    # save summary
    print(f'Writing XML file')
    with open(output_pathname, 'wb') as f:
        f.write(lxml.etree.tostring(testsuites, pretty_print=True))

    return test_cases, testsuites


def generate_test_summary(
        input_folder='.',
        required_tests=[],
        output_filename=None,
        output_formats=['rst', 'pdf'],
        title='Test Summary Report'):
    """ Load all junit or xreport-legacy XML test reports in the specified folder and generate a
    summary report that retains the latest result for every test.

    Parameters:
        input_folder (str): folder form which the xml files will be loaded.

        required_test (list): list of paths describing which tests are
            expected, and in which order. A missing test is considered to be
            failed. paths are typically in the format
            'module_name:class_name.method_name'.

        output_filename (str): if specified, the summary report is saved in
            the format determined by the extension. A combined Junit XML
            report is always saved with the same name but with the .xml
            extension.

        output_formats (list): File formats in which the test report will be
            saved.

        title (str): Title of the generated summary report
    """
    logger = logging.getLogger('')
    logger.info('start generate test summary')
    report_date = datetime.datetime.now().isoformat()
    print(f'generate_test_summary(input_folder={input_folder}, '
          f'required_tests={required_tests}, output_filename={output_filename}, '
          f'title={title}')
    # Get the aggregate test cases from the input folder
    test_cases, _ = generate_aggregate_junit(input_folder=input_folder)

    # Split into required/optional tests
    required_test_cases = []
    optional_test_cases = []
    for nodeid, tcs in test_cases.items():
        if nodeid in required_tests:
            required_test_cases.append(tcs)
        else:
            optional_test_cases.append(tcs)

    # Create an empty RestructuredText document
    rst = rST()

    # Add Title and Table of Contents
    rst.add_section(title, level=0)
    rst.add_toc(depth=5)

    # Add Context info
    rst.add_section("Summary info", level=1)
    rst.add_table([
        ['Report date/time', report_date],
        ['Target file name', output_filename],
        ])
    # report.add_group_info(
    #     test_name='Test Summary report',
    #     title=title,
    #     test_path='(summary)',
    #     test_date=test_date
    #     )

    # Add Summary tables
    rst.add_section("Required Tests Summary", level=1)
    rst.add_table([[tc.date, tc.nodeid, ('FAIL','PASS')[tc.passed], tc.status_message] for tc in required_test_cases])
    rst.add_section("Optional Tests Summary", level=1)
    rst.add_table([[tc.date, tc.nodeid, ('FAIL','PASS')[tc.passed], tc.status_message] for tc in optional_test_cases])

    # Add Test Results

    def add_test_results(title, test_cases):
        rst.add_section(title, level=1)
        for tc in test_cases:
            rst.add_section(tc.nodeid, level=2)
            rst.add_literal_block(''.join(tc.node.itertext()))
    add_test_results("Required Tests results", required_test_cases)
    add_test_results("Optional Tests results", optional_test_cases)

    if output_filename:
        rst.write(output_filename, output_formats)

    return rst






# pytest -v mgadc08_bench_tests.py::test_image -x --tb=long -l -rA --html www.html --junit-xml=xml.xml -o junit_logging=all


if __name__ == "__main__":
    generate_test_summary('./data',output_filename='summary', output_formats=['rst', 'pdf', 'html'])