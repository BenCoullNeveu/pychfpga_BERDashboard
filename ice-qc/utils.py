from functools import partial 

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
            return 'Maybe ({})'.format(self._value)

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

class TestUtils:
    """ Some utility methods common to all tests. 
    """
    def open_instrument(self, name):
        """ Looks up the instrument name in the instrument table in configuration file and open it with the parameters specified in the table.  
        """
        instr_params = self.cfg.instruments[name].copy()
        class_name = instr_params.pop('labpy_object')
        return labpy.open_instrument(class_name, **instr_params)

    def open_ps(self, name='ps16v', voltage=None, current=None):
        """ Opens a power supply and configures it

        The `voltage` and `current` to be programmed can be specified. If `None`, the global values from
        the config file in ``motherboard_tests.global_settings`` will be
        used.
        """
        
        # open power supply instrument if it is in the list of instruments and if we don't force manual operation /self.cfg.get('manual_ps', False)/
        if True and name in self.cfg.instruments:
            print("Tried to connect")
            self.ps = self.open_instrument(name)
        else:
            self.ps = None


        # initialize power supply if we have one
        if name == 'ps18v' and self.ps:
            voltage = voltage if voltage is not None else self.cfg.motherboard_tests.global_settings.ps_voltage
            current = current if current is not None else self.cfg.motherboard_tests.global_settings.ps_current
            self.ps.set_output(state=False) #Ensuring power on N5764A is off
            self.ps.clear() #Clearing any previous protection
            self.ps.set_voltage(voltage=voltage) #Setting voltage to 18V, power still off
            self.ps.set_current_limit(current=current, ocp=True) #Setting current limit and turning on ocp feature


        if name == 'ps16v' and self.ps:
            voltage = voltage if voltage is not None else self.cfg.motherboard_tests.global_settings.ps_voltage
            current = current if current is not None else self.cfg.motherboard_tests.global_settings.ps_current
            self.ps.set_output(state=False)
            #self.ps.set_current_limit(current=current)


        return self.ps
