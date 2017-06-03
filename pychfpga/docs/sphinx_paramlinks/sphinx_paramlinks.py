#!coding: utf-8
import re
from docutils import nodes
from docutils.transforms import Transform
import os
from sphinx.util.osutil import copyfile
from sphinx.util.console import bold
from sphinx.roles import AnyXRefRole
from sphinx.domains.python import PythonDomain
from distutils.version import LooseVersion
from sphinx.util.nodes import make_refnode
from sphinx.util.compat import Directive
from sphinx import addnodes

from sphinx import __version__
from sphinx.domains import ObjType

PARAMLINK_CLASS_NAME = 'paramlink' # class applies to references and targets for use by the CSS
PARAMLINK_INDEX_NAME = '_sphinx_paramlinks_index' # make of the fake index entry used to hold temporary parameter link info
PARAMETER_TYPE = 'parameter'
OBJ_TYPE_KEY = 'py:obj_type'
OBJ_PATH_KEY = 'py:obj_path'


# PARAM_REF_ID_SEPARATOR = '.params.'  # could be just a '.', really
PARAM_OBJECT_SEPARATOR = '>' # Separator between the method and parameter names in object table. Don't use '.', or the standard resolve_any_xref() will dig up all the references to parameter with that named across the whole documentation.
PARAM_REF_ID_SEPARATOR = '>' # Separtor between the method and parameter in the reference IDs (reference links). Could be just a '.', really. The search page will work if the REF_ID separator is the same as the OBJECT separator.

NO_PARAM_LIST = ['None']

PARAM_MARKER = "_sphinx_paramlinks_"  # used to uniquely tag the parameter text so it can be unambiguously identified and re-processed.
verbose = 1 # Print messages: 0: never, 1: if errors, 2: if warnings, 3: info

def _is_html(app):
    return app.builder.name in ('html', 'readthedocs')

def paramname_from_param_text(paramname, strip_markup=False):
    """ Extract the parameter name from the parameter text """
    # if the param name is in a literal block (e.g. ``param_name``, extract just the name
    literal_match = re.match(r'^``(.+?)``$', paramname)
    if literal_match:
        paramname = literal_match.group(1)
    refname = paramname
    # If a default value was given in the form  param_name=some_value, extract just the parameter name
    eq_match = re.match(r'(.+?)=.+$', refname)
    if eq_match:
        refname = eq_match.group(1)
    # Remove backslashes if `strip_markup` is ``True``
    if strip_markup:
        refname = re.sub(r'\\', '', refname)
    return refname

def make_refid(parent_object_name, param_name):
    """ Build the reference ID of a parameter from the parent object name and its parameter name"""
    if PARAM_REF_ID_SEPARATOR in param_name or PARAM_OBJECT_SEPARATOR in param_name:
        raise RuntimeError("Parameter names mush not contain '%s' or '%s'" % (PARAM_REF_ID_SEPARATOR, PARAM_OBJECT_SEPARATOR))
    return '%s%s%s' % (parent_object_name, PARAM_REF_ID_SEPARATOR, param_name)

def refid_to_objectname(refid):
    """ replace the last '.params.' with a '>' """
    return PARAM_OBJECT_SEPARATOR.join(refid.rsplit(PARAM_REF_ID_SEPARATOR, 1))

def objectname_to_refid(object_name):
    """ replace '>' with '.params.' """
    return object_name.replace(PARAM_OBJECT_SEPARATOR, PARAM_REF_ID_SEPARATOR)

def encode_param_text(object_name, param_text):
    """ Create an identifiable string that contain the object name and parameter text"""
    if '.' in param_text:
        raise RuntimeError("Parameter text ('%s') must not contain '.'" % param_text)
    return "%s%s.%s" % (PARAM_MARKER, object_name, param_text)

def is_encoded_param_text(text):
    """ True if `text` is encoded parameter text

    Parameters:
        text (str): text to check

    Returns:
        (bool)
    """
    return text.startswith(PARAM_MARKER)

def decode_param_text(text):
    """ Split encoded text ack into object name and parameter text """
    components = re.match(r'%s(.+)\.(.+)$' % PARAM_MARKER, text)
    object_name, param_text = components.group(1, 2)
    return object_name, param_text

def autodoc_process_docstring(app, what, name, obj, options, lines):
    """ ``autodoc`` hook to pre-process parameter entries.

    The following is done:
        - Add the ``currentobject`` directive to the docstrings to help partial reference loopup
             (see `lookup_reference`)
        - Mangle the parameter names found in
             ``:param:`` by prefixing a constant string and the reference id to the parameter name so we can
             later find these names and create target nodes with that id (see `LinkParams`),
        - Add an index entry for the parameter in a temporary
             collection so we can augment the document index AND the object reference table.

    e.g::

        :param modifier param_name::

    becomes::

        .. currentobject object_type packagename.modulename.classname.methodname
        :param modifier _sphinx_paramlink_pathtoparentobject.params.param_name: ...

    """
    docname = app.env.temp_data['docname']

    idx = app.env.indexentries.setdefault(PARAMLINK_INDEX_NAME, {})

    doc_idx = idx.setdefault(docname, [])

    def _cvt_param(name, line):
        # if name.endswith(".__init__"):
        #     # kill off __init__ if present, the links are always
        #     # off the class
        #     name = name[0:-9]

        def cvt(m):
            objname = name
            modifier, param_text, desc = m.group(1) or '', m.group(2), m.group(3)
            # skip if the docstrings get processed multiple times
            param_name = paramname_from_param_text(param_text, strip_markup=True)
            if param_name in NO_PARAM_LIST:
                return m.group()
            # item = ('single', 'paramname (path_to_method parameter)', 'path_to_method.params.paramname', '')
            index_name = '%s (%s parameter)' % (param_name, objname.rsplit('.', 1)[-1])
            target_id = make_refid(objname, param_name)
            # print 'target_id=', target_id
            index_item = ('single', index_name, target_id, '')
            if LooseVersion(__version__) >= LooseVersion('1.4.0'):
                index_item += (None,)
            # Dont add the same index entry twice: it messes up crossrefs by causing false multipel matches
            if index_item in doc_idx:  # use a set() for more efficiency
                if verbose >= 2:
                    print 'PARAMLINKS: Warning: index for param %s already exists. Leaving it as is as %s' % (param_text, m.group())
            else:
                doc_idx.append(index_item)
            # print 'encoding :',param_text, '***in***', m.group()
            # return ":param %s%s:" % (  # modifier includes trailing space(s)
            #         modifier, encode_param_text(objname, param_text))
            if ':paramtarget:' in desc:
                if verbose >= 2:
                    print 'PARAMLINKS: Warning: param %s already processed. Skipping. line=%s' % (param_text, m.group())
                return m.group()
            else:
                return ":param %s%s: :paramtarget:`%s` %s" % (  # modifier includes trailing space(s)
                    modifier, param_text, param_name, desc)
        newline = re.sub(r'^:param ([^:]+? )?([^:]+?):(.*)', cvt, line)
        if newline != line and verbose >=3:
            print 'PARAMLINK (in %s): modified "%s" to "%s"' % (name, line, newline)

        return newline


    # If the docstrings do not already contain a ``.. currentobject::`` directive, add one at the top.
    if not any(line.strip().startswith(':currentobject:') for line in lines):
        # Add the ``currentobject`` directive to help the reference to find their target
        # pos = min(len(lines), 1)
        if lines:
            lines[0] = (':currentobject:`%s` '% name) + lines[0]
        # lines.insert(0, '.. currentobject:: %s %s' % (what, name))
        # lines.insert(1, '')
    else:
        if verbose >= 2:
           print 'PARAMLINKS: Warning: object %s already has a currentobject directive. Skipping' % name

    # Process docstring lines to add a :paramtarget:`param_name` at the befinning of the description of each :param:
    if what in ('function', 'method', 'class'):
    # if True or callable(obj):
        if verbose >= 3:
            print 'PARAMLINKS: processing autodoc strings on %s object %s in file %s' % (what, name, docname)
        lines[:] = [_cvt_param(name, line) for line in lines]



class LinkParams(Transform):
    """
    Apply references targets and optional references to nodes that contain our target text.
    """
    default_priority = 210

    def apply(self):
        # return
        # seach <strong> nodes, which will include the titles for
        # those :param: directives, looking for our special token.
        # then fix up the text within the node and create a target node.
        # for ref in self.document.traverse(nodes.strong):
        for xref in self.document.traverse(addnodes.pending_xref):
            if xref['reftype'] != 'paramtarget':
                continue

            # or OBJ_PATH_KEY not in xref

            param_name = xref['reftarget']

            if verbose >= 3:
                print 'PARAMLINKS.LinkParams: found :%s:%s'% ( xref['reftype'],  param_name)

            object_name = xref[OBJ_PATH_KEY]

            # text = ref.astext()

            # In domain 'py', ':param:' is a TypedField
            #
            # As per sphinx.utils.docfields.TypedField.make_field(and also GroupedField), the
            # parameter name is the first node of the nodes.paragraph() that also contains the
            # parameter description
            ref = xref
            while ref and not isinstance(ref, nodes.paragraph):
                ref = ref.parent
            if not ref:
                raise RuntimeError('PARAMLINKS.LinkParams: cound not find parameter container paragraph...')

            # text = xref['reftarget']

            # print 'PARAMLINKS: found :', text
            # print list(ref.traverse(ascend=True, descend=True))
            # if is_encoded_param_text(text):


            # Extract the path to the object (method/funciton) from the parameter name

            # ref = ref.parent.parent[0]
            # object_name, param_text = decode_param_text(text)
            # param_name = paramname_from_param_text(param_text)

            refid = make_refid(object_name, param_name)
            ref.insert(0, nodes.target('', '', ids=[refid]))

            # del ref[0]
            # ref.insert(0, nodes.Text(param_text, param_text))

            xref.parent.remove(xref)

            is_html = _is_html(self.document.settings.env.app)
            if is_html:
                # add the "p" thing only if we're the HTML builder.

                # using a real ¶, surprising, right?
                # http://docutils.sourceforge.net/FAQ.html#how-can-i-represent-esoteric-characters-e-g-character-entities-in-a-document

                # "For example, say you want an em-dash (XML
                # character entity &mdash;, Unicode character
                # U+2014) in your document: use a real em-dash.
                # Insert concrete characters (e.g. type a real em-
                # dash) into your input file, using whatever
                # encoding suits your application, and tell
                # Docutils the input encoding. Docutils uses
                # Unicode internally, so the em-dash character is
                # a real em-dash internally."   OK !

                # for pos, node in enumerate(ref.parent.children):
                #     # try to figure out where the node with the
                #     # param_text is. thought this was simple, but
                #     # readthedocs proving..it's not.
                #     # TODO: need to take into account a type name
                #     # with the parens.
                #     if isinstance(node, nodes.TextElement) and \
                #             node.astext() == param_text:
                #         break
                # else:
                #     return

                sep = ref.traverse(lambda n:n.astext() ==' -- ')[0]  # a Text (Node) node
                newsep = nodes.Text('-- ')
                # print sep.parent.pformat()
                # print 'index=', sep.parent.index(sep)
                sep.parent.replace(sep, newsep)
                # xref.replace_self(
                newsep.parent.insert(
                    newsep.parent.index(newsep),
                    nodes.reference(
                        '', '',
                        nodes.Text(u"¶", u"¶"),
                        refid=refid,
                        # paramlink is our own CSS class, headerlink
                        # is theirs.  Trying to get everything we can for
                        # existing symbols...
                        classes=[PARAMLINK_CLASS_NAME, 'headerlink']
                    )
                )



def lookup_reference(app, env, node, contnode):
    """
    Catch any unresolved "pending xref" nodes (including parameter references) and resolve them by using the
    the object hierarchy information stored with the ``currentobject`` directive to gradually
    narrow  down the search scope until there is only one solution.

    Both resolve_xref() and resolve_any_xref() cannot find parameter references on purpose
    because they are listed in the object table with their name merged with the parent object.

    If the parameter name was stored as a normal dot-separated hierarchical name, the  :any:
    reference would find  all references to a parameter with the same name in any method of a class
    and would fail.

    If an explicit path is provided with the reference, `lookup_reference` uses only that path.

    This mechanism also works for any standard object that fail because resolve_xref() and
    resolve_any_xref() found too many matches.

    The Sphinx BuildEnvironment then gives us one more chance to do this lookup by allowing
    registering `lookup_reference` to the "missing-reference" event using::

        app.connect('missing-reference', lookup_reference)
    """

    reftype = node['reftype']
    target = node['reftarget']
    refdoc = node.get('refdoc', None)
    obj_type = node.get(OBJ_TYPE_KEY, '')
    obj_path = node.get(OBJ_PATH_KEY, '')
    has_explicit_title= node['refexplicit']

    def find_objects(domain, targets):
        objects = env.domains[domain].data['objects']
        return {(objname, objdoc, objtype)
                for target_type, target_name in targets
                for objname, (objdoc, objtype) in objects.items()
                if ((not target_type or target_type == objtype)
                    and objname.endswith(target_name))}

    # if reftype in ['any', 'paramref']:

    # Extract the context info from the target name
    if '.' in target:  # if some context was provided
        context_name, param_name = target.rsplit('.', 1)
    else:
        context_name, param_name = ('', target)

    # Remove the leading '~' and set the display name (the text to be shown by the reference link)
    if context_name.startswith('~'):
        context_name = context_name[1:]
        display_name = param_name
    elif context_name:
        display_name = context_name + '.' + param_name
    else:
        display_name = param_name

    mess = []
    mess.append('PARAMLINKS LOOKUP :%s:`%s`' %  (reftype, target))
    mess.append('   Refnode attributes: %s' % node.attributes)
    mess.append('   Display name = %s' % display_name)

    # determine the search targets
    search_targets = []
    # If reftype is any or paramref, add a parameter search target which uses a '>' separator
    if reftype in ('any', 'paramref'):
        search_targets.append((PARAMETER_TYPE, context_name + '>' + param_name))
    # if we search for any element, then also look for any object
    if reftype == 'any':
        search_targets.append(('', context_name + '.' + param_name))

    if not search_targets:
        mess.append("   Unsupported reference type %s. Don't know what to search. No search performed" % reftype)
        if verbose >= 2:
            print '\n'.join(mess)
        return None

    mess.append("   Looking for %s" % (' or '.join('(%s:*%s)' % (tt or '*', tn)  for tt, tn in search_targets)))

    #if a context was provided with the target, well, that's what the customer want and we'll stick to that, even if we find no or multiple targets
    # Also fall back to an explicit search if the node does not contain context info (obj_path, added by the ``currentobject`` directive)
    if context_name or not obj_path:
        mess.append('   Searching objects %s only with provided context (in any). There is no object context info with the reference.' % search_targets)
        objects = find_objects('py', search_targets)
    # otherwise, search from the least specific context (no context at all), and gradually add
    # context until we have only one solution or no more solutions.
    else:
        mess.append('   Searching objects %s with the context found within the reference (obj_type=%s, obj_path=%s) ' % (search_targets, obj_type, obj_path))
        context_elements = obj_path.split('.')
        for depth in range(len(context_elements) + 1):  # from 0 to N context elements
            context = '.'.join(context_elements[-depth:]) if depth else '' # Context is the `depth` last elements
            contexted_targets = [(typ, context + name) for typ, name in search_targets]
            objects = find_objects('py', contexted_targets)
            mess.append('      Trying depth=%i: %i results (context=%s, targets = %s)' % (depth, len(objects), context, contexted_targets))
            # If we found no match, it won't get better with more context. Give up.
            # If we found one match only, that's good enough for us! Stop here!
            if len(objects) <= 1:
                break
            for object_name, _ , _ in objects:
                mess.append('         --> %s' % object_name)

    # Bail out if we dont have satisfactory results
    if not len(objects): # If no result
        mess.append("   Found nothing!")
        if verbose >= 1:
            print '\n'.join(mess)
        return None
    elif len(objects) > 1:  # if multiple results
        mess.append("   Found %i results. We want only one. No link is generated." % len(objects))
        if verbose >= 1:
            print '\n'.join(mess)
        return None

    # if only one result

    object_path, object_doc, object_type = objects.pop()
    mess.append('   Found object: %s' % object_path)
    ref = objectname_to_refid(object_path) # convert from mangled name back to link name
    mess.append('   Creating reference to: %s' % ref)

    # if the node does not have an explicit title, create a new content node with our display name
    # Add a specific class  name to the ref so we can style it
    if has_explicit_title:
        new_contnode = contnode
        new_contnode['classes'] += [PARAMLINK_CLASS_NAME]
    else:
        classes = contnode['classes'] + [PARAMLINK_CLASS_NAME]
        new_contnode = nodes.literal(text=display_name, classes= classes) # displayed content element inside the reference node


    if verbose >=3:
        print '\n'.join(mess)

    return make_refnode(app.builder, refdoc, object_doc, ref,
                        new_contnode, display_name)



def add_stylesheet(app):
    """Registers the stylesheet associated with this extension"""
    app.add_stylesheet('sphinx_paramlinks.css')


def copy_stylesheet(app, exception):
    """ Copy the stylesheet from the *extension source folder* to the to destination build folder. By
    default, Sphinx only copies stylesheets from the _static folder located at the root of the documentation
    folder.
    """
    app.info(
        bold('The name of the builder is: %s' % app.builder.name), nonl=True)

    if not _is_html(app) or exception:
        return
    app.info(bold('Copying sphinx_paramlinks stylesheet... '), nonl=True)

    source = os.path.abspath(os.path.dirname(__file__))

    # the '_static' directory name is hardcoded in
    # sphinx.builders.html.StandaloneHTMLBuilder.copy_static_files.
    # would be nice if Sphinx could improve the API here so that we just
    # give it the path to a .css file and it does the right thing.
    dest = os.path.join(app.builder.outdir, '_static', 'sphinx_paramlinks.css')
    copyfile(os.path.join(source, "sphinx_paramlinks.css"), dest)
    app.info('done')


def build_index(app, doctree):
    """ Add the reference to parameters to the index and to the main python object reference table
    to allow cross-reference resolution.

    The reference id of the parameter is in the format 'pathtomethod.params.paramname'.

    However, the name we use in the object table is modified to 'pathtomethod>paramname' so the
    default resolvers won't find it, because it will be confused if the parameter name exist in
    multiple methods/functions. Our fallback resolver `lookup_reference' will take care of those
    resolutions.
    """
    entries = app.env.indexentries.setdefault(PARAMLINK_INDEX_NAME, {})

    for docname, doc_entries in entries.items():
        # Add entries to index
        app.env.indexentries[docname].extend(doc_entries)

        # Add entries to object table
        for entry in doc_entries:
            sing, desc, ref, extra = entry[:4]
            mangled_ref = refid_to_objectname(ref) # replace the last '.params.' by '>'
            if verbose >= 3:
                print 'PARAMLINKS: build_index: adding ref %s = (%s, %s)' % (mangled_ref, docname, PARAMETER_TYPE)
            app.env.domains['py'].data['objects'][mangled_ref] = (docname, PARAMETER_TYPE)

    app.env.indexentries.pop(PARAMLINK_INDEX_NAME)

class PyCurrentObject(Directive):
    """
    Directive to tell Sphinx what object we are currently in (object type, object path). The
    'lookup_reference' hook uses this information solve references that the current
    Python domain can't, inluding paramter references.

    The object info is saved in ``env.ref_context`` and is tagged to AnyXrefRole references
    (``:any:`` and ``:paramref:`` or any other user-defined ones). It will be used to resolve those
    references when only partial references are provided.

    For those who want as little markup in their docs, this allows ``:any:`` to be is set as the
    default role, allowing references to method/function parameters to be done very succinctly with
    just ``\`param_name\```.


    Arguments:
        obj_type (str): Type of the current object (method, attribute, class etc.). For information only.
        obj_path (str): Full object hierarchy path to the current object.

    Example::
        .. currentobject:: method  mypackage.mymodule.myclass.mymethod

    Note:
        The ``currentobject`` directive is inserted automatically to autodocumented objects by the `autodoc_process_docstring` hook.

    Based on ``sphinx.domains.python.PyCurrentModule``
    """

    has_content = False
    required_arguments = 2
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {}

    def run(self):
        env = self.state.document.settings.env
        obj_type = self.arguments[0].strip()
        obj_path = self.arguments[1].strip()
        env.ref_context[OBJ_TYPE_KEY] = obj_type
        env.ref_context[OBJ_PATH_KEY] = obj_path
        return []


def currentobject_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
    if verbose >=3:
        print 'PARAMLINKS.currentobject_role: setting %s=%s' % (OBJ_PATH_KEY, text)
    env = inliner.document.settings.env
    env.ref_context[OBJ_PATH_KEY] = text
    return [], []

# vhdl_code_role.options = {'class': directives.class_option,
#                      'language': directives.unchanged}


# Add the 'parameter' object type and associate it with the role name
# We don't seem to need this
# PythonDomain.object_types[PARAMETER_TYPE] = ObjType(PARAMETER_TYPE, 'param')  # object_types[object_type_name] = ObjType(localized_name, role1, role2...)

def setup(app):

    app.add_directive('currentobject', PyCurrentObject)

    # PyXRefRole is what the sphinx Python domain uses to set up
    # role nodes like "meth", "func", etc.  It produces a "pending xref"
    # sphinx node along with contextual information.
    app.add_role_to_domain("py", "paramref", AnyXRefRole())  # Same as :any: role. Adds all possible context info to the reference, including our new py:method
    app.add_role_to_domain("py", "paramtarget", AnyXRefRole())  # Same as :any: role. Adds all possible context info to the reference, including our new py:method
    app.add_role_to_domain("py", "currentobject", currentobject_role)  #

    app.connect('autodoc-process-docstring', autodoc_process_docstring) # Modify parameter names for later identification and build parameter reference table
    app.add_transform(LinkParams) # Find modified parameter nodes and convert them to reference targets
    app.connect('doctree-read', build_index) # Copy parameter links to the object cross reference table and to the index
    app.connect('missing-reference', lookup_reference) # process references that were not resolved, including parameter references

    # Handle custom stylesheet
    app.connect('builder-inited', add_stylesheet)
    app.connect('build-finished', copy_stylesheet)
