class Maybe:
	"""
	General monad class for uncertain operation handling, (harware request, file opening, etc.). Maybe<T> objects can 
	contain a value of unknown type T and can be given through run() a function of type T -> K and will return a Maybe<K>. If
	the function encounters some problem and returns a None value, this None will propagate down the chain without crash, allowing
	the user to handle the failure.
	"""


    def __init__(self, value, errlog='Operation failed'):

    	"""
		Constructor method
    	"""
        self._value  = value
        self._errlog = errlog

    def run(self, func, errhandle=None):
    	"""
		Returns Maybe<K> when given a func: T -> K applied on Maybe<T> 

		:params func: Function T -> K to be applied to Maybe<T>
		:params errhandle: Function () -> K that allows the error handling to be specified by the user, default to unused
		:return: Outpu of the funciton wrapped in the Maybe class
		:rtype: Maybe<K>

    	"""

        if self._value is None:
        	print(_errlog)

        	if errhandle is not None:
        		return Maybe(errhandle())
        		

            return Maybe(None)
        else:
            return Maybe(func(self._value))

    def orElse(self, default):
    	"""
		Set a default value for Maybe<T> object when it is None

		:params default: Default value
    	"""

        if self._value is None:
            return Maybe(default)
        else:
            return self

    def unwrap(self):
		"""
		Removes the Maybe wrapper from object and returns its reference

		"""

        return self._value

    def __or__(self, other):
        return Maybe(self._value or other._value)

    def __str__(self):
        if self._value is None:
            return 'Nothing'
        else:
            return 'Just {}'.format(self._value)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if isinstance(other, Maybe):
            return self._value == other._value
        else:
            return False

    def __ne__(self, other):
        return not (self == other)

    def __bool__(self):
        return self._value is not None