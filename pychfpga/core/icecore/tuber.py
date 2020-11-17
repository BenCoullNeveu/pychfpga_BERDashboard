'''
Tuber object interface


2020-11-04 JFC: Proposed changes, to be discussed:

    Make tuber_objname an attribute
'''
# Standard library packages
import socket
import urllib
import asyncio
import atexit
import textwrap
import warnings

# PyPi packages
import aiohttp
import nest_asyncio

# local packages
from . import tworoutine

# Simplejson is now mandatory (it's faster enough to insist)
import simplejson

__all__ = [
    "TuberError", "TuberRemoteError",
    "TuberCategory", "TuberObject",
]


class TuberError(Exception):
    pass

class TuberStateError(TuberError):
    pass

class TuberNetworkError(TuberError):
    pass

class TuberRemoteError(TuberError):
    pass


class TuberResult:
    def __init__(self, d):
        self.__dict__.update(d)

    def __iter__(self):
        return iter(self.__dict__.values())

    def __repr__(self):
        'Return a nicely formatted representation string'
        return 'TuberResult({0})'.format(
            ','.join('{0}={1!r}'.format(name, val)
                     for name, val in self.__dict__.items()))


def valid_dynamic_attr(name):
    """
    Return True if the input attribute name can be assigned to a dynamically
    created attribute (i.e. an attribute that would be returned by a call to
    `_tuber_get_meta()`), False otherwise.  See documentation of the
    `TuberObject.__getattr__` method for a discussion of why this function
    is necessary.
    """
    # These are mostly hints for SQLAlchemy or IPython.

    if name.startswith((
            '__', '_sa', '_tuber_meta', '_repr',
            '_ipython', '_orm', '_tworoutine__', '_calls',
    )):
        return False

    if name in {'trait_names', '_getAttributeNames', 'getdoc', '_tuber_get_meta'}:
        return False

    return True


class Context(tworoutine.tworoutine):
    '''A context container for TuberCalls. Permits calls to be aggregated.

    Using this interface, you can write code like:

        #>>> from pydfmux import Dfmux, macro, asynchronously, Return

        #>>> @pydfmux.macro(Dfmux)
        #... def my_macro(d):
        #...     with d.tuber_context() as ctx:
        #...         p = ctx.get_mezzanine_power(2)
        #...         f = yield ctx.get_frequency(ctx.UNITS.HZ, 1, 1, 1)
        #...         ctx.set_frequency(f+1, ctx.UNITS.HZ, 1, 1, 1)
        #...         yield asynchronously(ctx)
        #...     raise Return((yield p))

        #>>> my_macro(d)
        #True

    Commands are dispatched to the board strictly in-order, but are
    automatically bundled up to reduce traffic. In this example, the first two
    calls are dispatched together, since the result 'p' is not used until
    later.

    There are a couple of important considerations:

        * Calls made on 'ctx' return Futures, which can be converted into
          their results via 'yield'.

        * The final 'yield asynchronously(ctx)' ensures the context queue is
          flushed. It's only necessary if you don't yield the results of the
          final call in the context. If you need this yield and leave it out,
          you'll see a warning and your code will dispatch synchronously (i.e.
          other work in the asynchronous framework won't get done in the
          meantime.)

    Note that you will *not* catch exceptions unless you check for them
    explicitly. For example, in this code:

        #>>> with d.tuber_context() as ctx:
        #...     p = ctx.get_mezzanine_power(3)

    the function call is executed, and generates an exception. The exception is
    embedded in 'p' and will not be raised unless you call 'p.result()'!

    Adjust the `connect_timeout` and `request_timeout` attributes of the ctx
    object to change the connect and request timeouts. The default value
    (1800 seconds) allows calls to the board to be quite slow.
    '''

    def __init__(self, obj, **ctx_kwargs):
        self.calls = []
        self.connect_timeout = 1800
        self.request_timeout = 1800
        self.obj = obj
        self.ctx_kwargs = ctx_kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.calls:
            self()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        '''Ensure the context is flushed.'''

        if self.calls:
            await self.__acall__()

    def _add_call(self, **request):

        future = asyncio.Future()

        # Ensure call is made in the correct context
        objname = request.setdefault('object', self.obj.tuber_objname)
        assert objname == self.obj.tuber_objname, \
            f'Got call to {objname} in context for {self.obj.tuber_objname}'

        self.calls.append((request, future))

        return future

    async def __acall__(self):
        '''Break off a set of calls and return them for execution.'''

        calls = []
        futures = []
        while self.calls:
            (c, f) = self.calls.pop(0)

            calls.append(c)
            futures.append(f)

        if calls:
            # Create a HTTP request to complete the call. This is a coroutine,
            # so we queue the call and then suspend execution (via 'yield')
            # until it's complete.
            session = self.obj.get_client_session()
            # print(f'URI={self.obj.tuber_uri}, arg = {calls}')
            try:
                async with session.post(self.obj.tuber_uri, json=calls) as resp:
                    json_out = await resp.json(
                            loads=simplejson.JSONDecoder(object_hook=TuberResult).decode,
                            content_type=None)
                    # print(f'result: {json_out}')
            except aiohttp.ClientConnectorError as e:
                print('Network error')
                raise TuberNetworkError(e)

            # Resolve futures
            results = []
            for (f, r) in zip(futures, json_out):
                if hasattr(r, 'error') and r.error:
                    f.set_exception(TuberRemoteError(r.error.message))
                else:
                    results.append(r.result)
                    f.set_result(r.result)

            # Return a list of results
            return results

    def __getattr__(self, name):

        # Refuse to __getattr__ a couple of special names used elsewhere.
        if not valid_dynamic_attr(name):
            raise AttributeError("'%s' is not a valid method or property!" % name)

        # Queue methods calls.
        def caller(*args, **kwargs):

            # Add extra arguments where they're provided
            kwargs = kwargs.copy()
            kwargs.update(self.ctx_kwargs)

            # ensure that a new unique future is returned
            # each time this function is called
            future = self._add_call(method=name, args=args, kwargs=kwargs)

            return future

        setattr(self, name, caller)
        return caller


class TuberCategory:
    '''Pull Tuber functions into ORM objects based on categories.

    Here's an example. If "ib" is an IceBoard object, and you have the
    ordinary IceBoard function set_mezzanine_power(), you can run the
    following:

        >>> ib.set_mezzanine_power(True, 1)

    You also have the following ORM object:

        >>> m = ib.mezz1
        >>> print m.mezz_number
        1

    Rather than accessing mezzanine methods through the IceBoard, it
    seems more logical to do things like this:

        >>> m.set_mezzanine_power(True)

    The TuberCategory decorator allows this kind of call. Borrowing from
    FMCMezzanine again, we invoke the TuberCategory decorator as follows:

        @tuber.TuberCategory("Mezzanine", lambda m: m.iceboard,
            {"mezzanine": lambda m: m.mezz_number })
        class FMCMezzanine(HWMResource):
            [...]

    The decorator intercepts Tuber functions that claim to be members
    of the "Mezzanine" category, and using the FMCMezzanine object's
    mezz_number property, fills in "mezzanine" parameters before
    dispatching the function call back to the mezzanine's "iceboard"
    property.

    "Categories" are exported by C code. For example, try the following:

        $ curl -d '{"object":"IceBoard","property":"set_mezzanine_power"}' \
                http://iceboard004.local/tuber|json_pp

    This shell command asks the IceBoard to describe its 'set_mezzanine_power'
    call. The response includes:

        "categories": [ "IceBoard", "Mezzanine" ]'
    '''

    def __init__(self, category, getobject, **arg_mappers):
        self.category = category
        self.getobject = getobject
        self.arg_mappers = arg_mappers

    def __call__(decorator, cls):

        def tuber_context(self):
            obj = decorator.getobject(self)
            kwargs = {n: f(self) for (n, f) in decorator.arg_mappers.items()}
            return Context(obj, **kwargs)

        cls.tuber_context = tuber_context

        def __getattr__(self, name):
            '''This is a fall-through replacement for __getattr__.

            We assume we're capturing a function call that's missing
            arguments. We fill in these arguments and dispatch the call.

            See `TuberObject.__getattr__` for details.
            '''

            # Refuse to __getattr__ a couple of special names used elsewhere.
            if not valid_dynamic_attr(name):
                raise AttributeError("'%s' is not a valid method or property!" % name)

            parent = decorator.getobject(self)

            # Raise an Attribute error if the parent board isn't set
            if parent is None:
                raise AttributeError("'%s' is not a valid method or property!" % name)
            m = getattr(parent, name)

            if isinstance(m, tworoutine.tworoutine):

                @tworoutine.tworoutine
                async def acall(*args, **kwargs):
                    mapped_args = {
                        n: f(self)
                        for (n, f) in decorator.arg_mappers.items()
                    }

                    return await (~m)(*args, **kwargs, **mapped_args)

                return acall

            raise AttributeError("'%s' is not a valid method or property!" % name)

        cls.__getattr__ = __getattr__

        def __dir__(self):
            '''Retrieve a list of class properties/methods that are relevant.

            We try to grab the original list of attributes from the ORM,
            and then augment it with any Tuber functions in our category.

            See `TuberObject.__dir__` for more details.
            '''

            d = set(dir(self.__class__))
            d.update(dir(super(self.__class__, self)))

            o = decorator.getobject(self)
            # Return just the static attributes if the board object isn't set
            # This can occur during construction of the ORM.
            if o is None:
                return sorted(d)
            (meta, metap, metam) = o._tuber_get_meta()

            for m in meta.methods:
                if hasattr(metam[m], 'categories') and \
                        decorator.category in metam[m].categories:
                    d.add(m)
            return sorted(d)

        cls.__dir__ = __dir__

        return cls

@atexit.register
@tworoutine.tworoutine
async def close_client_sessions():
    """ Close all client sessions
    """
    await asyncio.gather(*[c.close() for c in TuberObject._client_sessions.values()])

class TuberObject:
    '''A base class for TuberObjects.

    This is a great way of using Python to correspond with network resources
    over a HTTP tunnel. It hides most of the gory details and makes your
    networked resource look and behave like a local Python object.

    To use it, you should subclass this TuberObject.
    '''

    # Cache for the methods and properties offered by the ARM processor
    _tuber_meta = {}
    _tuber_meta_properties = {}
    _tuber_meta_methods = {}
    _tuber_meta_async_method_names = {}

    # Client session objects in use by each event loop.
    _client_sessions = {}

    # Parametrize the TCP connection limits. Can be overriden by subclasses.
    _client_connections_total = 0  # total number of simultaneous TCP connections (0 = no limit)
    _client_connections_per_host = 4  # total number of simultaneous TCP connections per host (None = no limit)
    _tuber_async_method_prefix = 'tuber'  # no _
    _tuber_async_method_suffix = 'async'  # no _

    _tuber_getattr_in_progress = False

    def tuber_context(self):
        return Context(self)

    @property
    def tuber_uri(self):
        '''Retrieve the URI associated with this TuberResource.'''
        raise NotImplementedError("Subclass needs to define tuber_uri!")
    # tuber_uri = "http://10.10.10.244/tuber"

    @property
    def tuber_objname(self):
        '''Retrieve the Tuber Object associated with this TuberResource.'''
        return self.__class__.__name__

    # Configure the max clients to be 4 per TuberObject (IceBoard).

    def get_client_session(self):
        """
        Return a client session that was created in the currently running
        ioloop. If none exist, one is created.

        Sessions can be shared between multiple instances of TuberObject.

        The client session objects are tied to the event loop that was current
        when the session client is created. Using it in another ioloop causes
        problems.
        """
        loop = asyncio.get_event_loop()
        if loop in self._client_sessions:
            return self._client_sessions[loop]
        else:
            print(f'Running in new loop {id(loop)}. Creating new session with {self._client_connections_total} and {self._client_connections_per_host}')
            connector = aiohttp.TCPConnector(
                limit=self._client_connections_total,
                limit_per_host=self._client_connections_per_host)
            session = aiohttp.ClientSession(
                json_serialize=simplejson.dumps,
                connector=connector)
            self._client_sessions[loop] = session
            return session

    # tuber_objname = "IceBoard"


    @property
    def __doc__(self):
        '''Construct DocStrings using metadata from the underlying resource.'''

        (meta, _, _) = self._tuber_get_meta()

        return f"{meta.name}:\t{meta.summary}\n\n{meta.explanation}"

    def __dir__(self):
        '''Provide a list of what's here. (Used for tab-completion.)

        This function calls the `_tuber_get_meta()` method to get a list of
        methods and properties stored on the board. If an error occurs in
        communicating with the board, then this function returns an empty list,
        and future calls to `_tuber_get_meta()` do not attempt to access the
        board.  Use the `set_tuber_inspect(True)` module-level function to
        re-enable communication with the board.
        '''
        if self.tuber_uri not in self._tuber_meta:
            self._tuber_get_meta()
        return super().__dir__()

    #     # print('DIR called')
    #     attrs = dir(super(self.__class__, self))
    #     try:
    #         (meta, _, _) = self._tuber_get_meta()
    #     except Exception as e:
    #         print(f'Exception {e}')
    #         raise
    #     # print(f'dir={attrs}, {meta.properties}')
    #     # print('DIR comleted')
    #     return sorted(attrs + meta.properties + meta.methods + list(self._tuber_meta_async_method_names[self.tuber_uri].keys()))
    #     # return attrs

    @tworoutine.tworoutine
    async def _tuber_get_meta(self):
        '''Retrieve metadata associated with the remote network resource.

        This data isn't strictly needed to construct "blind" JSON-RPC calls,
        except for user-friendliness:

           * tab-completion requires knowledge of what the board does, and
           * docstrings are useful, but must be retrieved and attached.

        This class retrieves object-wide metadata, which can be used to build
        up properties and values (with tab-completion and docstrings)
        on-the-fly as they're needed.

        If tuber inspection has been disabled (either automatically when
        an error was encountered while calling this function in an attempt
        at tab-completion, or manually by calling `set_tuber_inspect(False)`),
        then this function returns empty lists.
        '''
        print(f'{self!r} Fetching Tuber metadata')

        if self.tuber_uri in self._tuber_meta:
            return (self._tuber_meta[self.tuber_uri],
                    self._tuber_meta_properties[self.tuber_uri],
                    self._tuber_meta_methods[self.tuber_uri])


        async with self.tuber_context() as ctx:
            # Just specify the object type, which returns the meta info.
            ctx._add_call()
            meta = await ctx.__acall__()
            meta = meta[0]

            # Query info on all properties
            for p in meta.properties:
                ctx._add_call(property=p)
            prop_list = await ctx.__acall__()

            for m in meta.methods:
                ctx._add_call(property=m)
            meth_list = await ctx.__acall__()
            # import traceback
            # try:
            #     gla
            # except Exception as err:

            #     print(traceback.print_tb(err.__traceback__))

            props = dict(zip(meta.properties, prop_list))
            methods = dict(zip(meta.methods, meth_list))


        def to_async_name(name):
            if name.startswith('_'):
                return '_%s_%s_%s' % (self._tuber_async_method_prefix, name[1:], self._tuber_async_method_suffix)
            else:
                return '%s_%s_%s' % (self._tuber_async_method_prefix, name, self._tuber_async_method_suffix)


        self._tuber_meta_properties[self.tuber_uri] = props
        self._tuber_meta_methods[self.tuber_uri] = methods
        self._tuber_meta[self.tuber_uri] = meta
        # Add properties to class attributes
        for name, value in props.items():
            # Store as class attribute
            print(f'Adding property {name} to {self}')
            setattr(TuberObject, name, value)

        # Add sync and async methods to class attributes
        for name, info in methods.items():
            async_name = to_async_name(name)

            # meth = tworoutine.tworoutine(self._get_async_method(name, info))
            # print(f'Adding method {name} to {self.__class__}')
            # setattr(TuberObject, name, meth)

            async_meth = self._get_async_method(name, info)
            print(f'Adding method {async_name} to {self.__class__}')
            setattr(TuberObject, async_name, async_meth)

    @staticmethod
    def _get_async_method(name, method_info):
        """
        """
        async def invoke(self, *args, **kwargs):
            async with self.tuber_context() as ctx:
                result = getattr(ctx, name)(*args, **kwargs)
            return result.result()
        invoke.__doc__ = textwrap.dedent('''
            {name}({args_short})

            {args_long}

            {explanation}''').format(
                name=name,
                args_short=', '.join([a.name for a in method_info.args]),
                args_long='\n'.join([
                    "    {:<16} {}".format(
                        arg.name + ":",
                        arg.description
                    ) for arg in method_info.args]),
                explanation='\n'.join(textwrap.wrap(method_info.explanation))
            )
        return invoke


    def __getattr__(self, name):
        '''Remote function call magic.

        This function is called to get attributes (e.g. class variables and
        functions) that don't exist on "self". Since we build up a cache of
        descriptors for things we've seen before, we don't need to avoid
        round-trips to the board for metadata in the following code.

        This function is only called for attributes that aren't yet bound
        to the instance (e.g. in the class definition or set using `setattr`).
        Thus, when an attribute is requested that has not yet been bound,
        it is first filtered through the `valid_dynamic_attr()` function
        to determine whether it is likely that the attribute is one that
        comes from the board.  If not, an AttributeError is raised; this
        is important to avoid making tuber calls to the board for attributes
        that are not bound by construction, such as attributes that
        sqlalchemy or ipython checks for to determine how it should interact
        with a given object.  If the input name is not first checked with
        `valid_dynamic_attr()`, it is possible to trigger nasty recursion
        depth errors by trying to access an attribute that does not
        exist on the board.
        '''

    #     # Refuse to __getattr__ a couple of special names used elsewhere.
    #     if not valid_dynamic_attr(name):
    #         raise AttributeError(f"'{name}' is not a valid method or property!")
    #     print('--------------------------------------------------------')
    #     print(f'getattr:{name}, loop={asyncio.get_event_loop()} ID={id(asyncio.get_event_loop())}')
    #     print('--------------------------------------------------------')
    #     # Make sure this request corresponds to something in the underlying
    #     # TuberObject.
        # print(f'Tuber.getattr {name}')

        # We set self._tuber_getattr_in_progress during the getattr process to
        # avoid infinite recursion in case anything we call (e.g. repr(self)
        # etc) accesses an unknown attribute.
        try:
            if self._tuber_getattr_in_progress or self.tuber_uri in self._tuber_meta:
                # return getattr(super(), name)
                raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, name))
                # if self._tuber_getattr_in_progress:
                #     raise RuntimeError(f'Tuber: trying to get attribute {name} while lookup for {self._tuber_getattr_in_progress} is in progress')
            else:
                self._tuber_getattr_in_progress = True
                self._tuber_get_meta()
                return getattr(self, name)
        finally:
            self._tuber_getattr_in_progress = False

        # raise AttributeError()
        # return super().__getattr__(name)

    #     async_names = self._tuber_meta_async_method_names[self.tuber_uri]

    #     # try:
    #     #     (meta, metap, metam) = (
    #     #         m[self.tuber_uri],
    #     #         mp[self.tuber_uri],
    #     #         mm[self.tuber_uri]
    #     #     )
    #     #     # (meta, metap, metam) = (
    #     #     #     self._tuber_meta[self.tuber_uri],
    #     #     #     self._tuber_meta_properties[self.tuber_uri],
    #     #     #     self._tuber_meta_methods[self.tuber_uri]
    #     #     # )
    #     # except KeyError as e:
    #     #     raise TuberStateError(e, "Attempt to retrieve metadata on TuberObject that doesn't have it yet! Did you forget to call resolve()?")
    #     # valid_names = meta.methods.keys() + meta.properties.keys() + ['async_' + n for n in meta.methods.keys()]
    #     # if name not in valid_names:
    #     #     raise AttributeError(f"'{name}' is not a valid method or property!")

    #     def create_docstring(method_info):
    #         return textwrap.dedent('''
    #             {name}({args_short})

    #             {args_long}

    #             {explanation}''').format(
    #                 name=name,
    #                 args_short=', '.join([a.name for a in method_info.args]),
    #                 args_long='\n'.join([
    #                     "    {:<16} {}".format(
    #                         arg.name + ":",
    #                         arg.description
    #                     ) for arg in method_info.args]),
    #                 explanation='\n'.join(textwrap.wrap(method_info.explanation))
    #             )



    #     # if name not in meta.methods and name not in meta.properties:
    #     #     raise AttributeError(f"'{name}' is not a valid method or property!")

    #     if name in meta.properties:
    #         # Store as a instance attribute
    #         setattr(self, name, metap[name])
    #         return getattr(self, name)

    #     elif name in meta.methods:
    #         # Generate a callable prototype
    #         @tworoutine.tworoutine
    #         async def invoke(self, *args, **kwargs):
    #             async with self.tuber_context() as ctx:
    #                 result = getattr(ctx, name)(*args, **kwargs)
    #             return result.result()

    #         invoke.__acall__.__doc__ = create_docstring(metam[name])
    #         # Associate as a class method.
    #         setattr(self.__class__, name, invoke)

    #     elif name in async_names:
    #         sync_name = async_names[name]
    #         async def invoke(self, *args, **kwargs):
    #             async with self.tuber_context() as ctx:
    #                 result = getattr(ctx, sync_name)(*args, **kwargs)
    #             return result.result()
    #         invoke.__doc__ = create_docstring(metam[sync_name])
    #         # Also add a pure async version of the method with the `async_` prefix
    #         setattr(self.__class__, name, invoke)
    #         return getattr(self, name)
    #     else:
    #         raise AttributeError(f"'{name}' is not a valid method or property!")

    # @tworoutine.tworoutine
    # async def sleep(self,t=5):
    #         await asyncio.sleep(t)

    # async def test(self):
    #     loop = asyncio.get_event_loop()
    #     nest_asyncio.apply(loop)
    #     print(f'Running in loop {id(loop)}')

    #     async def dot():
    #         while True:
    #             print('.',end='', flush=True)
    #             await asyncio.sleep(1)
    #     # loop.call_soon(dot())
    #     asyncio.create_task(dot())
    #     print('Calling sleep as coroutine')
    #     await self.sleep.cr()
    #     print('Calling sleep as synchronous function')
    #     self.sleep(5)

# patch the current interpreter loop
loop = asyncio.get_event_loop()
print(f'Enabling nested loop on interpreter event loop ID {id(loop)}')
nest_asyncio.apply(loop)
# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
