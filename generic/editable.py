
import json
from collections import namedtuple

from dispatch.events import Emitter

from atomic import AtomicStruct
from atomic.atomic_accelerator import AcceleratedAtomicStruct
from atomic.atomic_struct import SIMULATING_PLACEHOLDER
from rawdb.util.iter import auto_iterate
from math import lcm


#: See Editable.restrict
Restriction_ = namedtuple('Restriction', 'name min_value max_value min_length'
                          ' max_length validator children')


class Restriction(object):
    """Restriction definition on an attribute's value

    Methods
    -------
    restrict
        Add restrictions
    restrict_type
        Restrict values to a type
    validate
        Check that a new value is valid
    """
    def __init__(self, name, children=None, *args, **kwargs):
        self.name = name
        self.children = children or []
        self.validators = []
        self.restrict(*args, **kwargs)

    def restrict(self, *args, **kwargs):
        """Add value restrictions based on arguments

        Parameters passed must be as kwargs. If args are passed, that will
        represent a single validator with its arguments.

        Parameters
        ----------
        deferred : bool, optional
            If True, all function arguments will be evaluated at validation
            time returning the actual argument.
        values : iterable, optional
            List of all valid values
        min_value : optional
            Require value to be greater or equal to this value
        max_value : optional
            Require value to be less or equal to this value
        min_length : int, optional
            Require length of value to be greater or equal to this value
        max_length : int, optional
            Require length of value to be less or equal to this value
        divisible : int, optional
            Require all values to be divisible by this number
        child : dict, optional
            Apply restrictions on a container's children

        Examples
        --------
        >>> restriction = Restriction('name')
        >>> def value_is_even(editable, name, value):
                if value % 2:
                    raise ValueError('"{0}" is not even'.format(value))
        >>> restriction.restrict(value_is_even)
        >>> restriction.validate(object(), 'name', 2)
        >>> restriction.validate(object(), 'name', 3)
        Traceback (most recent call last):
            ...
        ValueError: "3" is not even!
        >>> restriction.restrict(min_value=7)
        >>> restriction.validate(object(), 'name', 8)
        >>> restriction.validate(object(), 'name', 4)
        Traceback (most recent call last):
            ...
        ValueError: "4" is less than mininum "7"
        >>> restriction.validate(object(), 'name', 9)
        Traceback (most recent call last):
            ...
        ValueError: "9" is not even!
        >>>
        """
        if kwargs.get('deferred'):
            idx = len(self.validators)
        if 'values' in kwargs:
            self.validators.append((self.validate_values, kwargs['values']))
        if 'min_value' in kwargs:
            self.validators.append((self.validate_min, kwargs['min_value']))
        if 'max_value' in kwargs:
            self.validators.append((self.validate_max, kwargs['max_value']))
        if 'min_length' in kwargs:
            self.validators.append((self.validate_min_length,
                                    kwargs['min_length']))
        if 'max_length' in kwargs:
            self.validators.append((self.validate_max_length,
                                    kwargs['max_length']))
        if 'divisible' in kwargs:
            self.validators.append((self.validate_mod, kwargs['divisible']))
        if 'type' in kwargs:
            self.restrict_type(kwargs['type'])
        if 'child' in kwargs:
            self.restrict_child(**kwargs['child'])
        if args:
            self.validators.append(args)
        if kwargs.get('deferred'):
            for i, validator in enumerate(self.validators[idx:], idx):
                func_args = []
                for j, arg in enumerate(validator[1:]):
                    if hasattr(arg, '__call__') and\
                            not hasattr(arg, '__base__'):
                        func_args.append(j)
                if func_args:
                    self.validators[i] = tuple([self.deferred_validate,
                                                validator[0], func_args] +
                                               list(validator[1:]))
        return self

    def restrict_type(self, type_, castable=True, *args):
        """Creates a type restriction

        Paramaters
        ----------
        type_ : type
            The type to restrict against
        castable : bool, optional
            If True (default), check to see if type_(value, *args) is valid.
            If False, check to see if value is an instance of type_
        """
        self.validators.append(tuple([self.validate_type, type_, castable] +
                                     list(args)))
        return self

    @property
    def child(self):
        """Restriction placed on a child"""
        try:
            return self._sub_restriction
        except:
            self._sub_restriction = Restriction(self.name)
            return self._sub_restriction

    def restrict_child(self, **kwargs):
        """Place restriction on a child, for use in containers

        Container validation must be explicitly called! Use a
        CollectionNotifier to get container updates

        Examples
        --------
        >>> parent = Restriction('name')
        >>> parent.restrict_child(type=int)
        >>> # Or parent.restrict(child={'type': int})
        >>> # Or parent.child.restrict_type(int)
        >>> parent.validate(object(), 'name', [13, 's', 15])
        ValueError: name: "s" is not a "int"!
        """
        self.child.restrict(**kwargs)
        self.validators.append((self.validate_children, self.child))
        return self.child

    @staticmethod
    def deferred_validate(editable, name, value, validate_func, func_args,
                          *args):
        args = list(args)
        for i in func_args:
            args[i] = args[i]()
        validate_func(*args)

    @staticmethod
    def validate_values(editable, name, value, values):
        if value not in values:
            raise ValueError(
                '{name}: "{value}" is not in "{restrict}"'
                .format(name=name, value=value, restrict=values))

    @staticmethod
    def validate_min(editable, name, value, min_value):
        if value < min_value:
            raise ValueError(
                '{name}: "{value}" is less than minimum "{restrict}"'
                .format(name=name, value=value, restrict=min_value))

    @staticmethod
    def validate_max(editable, name, value, max_value):
        if value > max_value:
            raise ValueError(
                '{name}: "{value}" is more than maximum "{restrict}"'
                .format(name=name, value=value, restrict=max_value))

    @staticmethod
    def validate_min_length(editable, name, value, min_length):
        if len(value) < min_length:
            raise ValueError(
                '{name}: "{value}" is shorter than mininum "{restrict}"'
                .format(name=name, value=value, restrict=min_length))

    @staticmethod
    def validate_max_length(editable, name, value, max_length):
        if len(value) > max_length:
            raise ValueError(
                '{name}: "{value}" is longer than maximum "{restrict}"'
                .format(name=name, value=value, restrict=max_length))

    @staticmethod
    def validate_mod(editable, name, value, mod):
        if not value % mod:
            raise ValueError(
                '{name}: "{value}" is not evenly divisible by {restrict}'
                .format(name=name, value=value, restrict=mod))

    @staticmethod
    def validate_type(editable, name, value, type_, castable=True, *args):
        if castable:
            obj = type_(value, *args)
            del obj
        else:
            if not isinstance(value, type_):
                raise ValueError(
                    '{name}: "{value}" is not a "{restrict}"'
                    .format(name=name, value=value, restrict=type_))

    @staticmethod
    def validate_children(editable, name, value, restriction):
        for child in auto_iterate(value)[2]:
            restriction.validate(editable, name, child)

    def validate(self, editable, name, value):
        """Check the validity of a new value by running against all validators

        Parameters
        ----------
        editable : object
            Object to pass to the validator functions. Validators may use
            this to get local information
        name : object
            Name of the attribute to pass to validator functions. Validators
            may use this to get local information
        value : mixed
            The new value to check

        Raises
        ------
        ValueError
            If the new value is not valid
        """
        for validator in self.validators:
            validator[0](editable, name, value, *validator[1:])

    def find_types(self):
        """Get all types associated with this Restriction.

        This retrieves the first argument for all functions passed that
        are named 'validate_type' (restrict_type does this automatically)

        Returns
        -------
        types : list
        """
        types = []
        for validator in self.validators:
            if validator[0].__name__ == 'validate_type':
                types.append(validator[1])
        return types

    def get_range(self):
        """Get a high and low value for this restriction.

        This pulls the highest argument of a min restriction and the lowest
        argument of a max restriction and the LCM of a mod restriction.

        Returns
        -------
        range : tuple(min, max, step)
        """
        min_value = None
        max_value = None
        step = None
        for validator in self.validators:
            func_name = validator[0].__name__
            if func_name == 'deferred_validate':
                func_name = validator[1].__name__
                if 0 in validator[2]:
                    arg = validator[3]()
                else:
                    arg = validator[3]
            else:
                arg = validator[1]
            if 'min' in func_name:
                if min_value is None:
                    min_value = arg
                else:
                    min_value = max(min_value, arg)
            elif 'max' in func_name:
                if max_value is None:
                    max_value = arg
                else:
                    max_value = min(max_value, arg)
            elif 'mod' in func_name:
                if step is None:
                    step = arg
                else:
                    step = lcm(step, arg)
        if min_value and step:
            for i in range(step):
                if not (min_value+i) % step:
                    min_value = min_value+i
                    break
        if max_value and step:
            for i in range(0, -step, -1):
                if not (max_value+i) % step:
                    max_value = max_value+i
                    break
        return (min_value, max_value, step)

    def get_values(self):
        """Get all valid values for this restriction.

        Returns
        -------
        values
        """
        values = None
        for validator in self.validators:
            if 'values' in validator[0].__name__:
                arg = validator[1]
                if values is None:
                    values = validator[1]
                else:
                    # TODO: handle complete merges of all types
                    for value in values:
                        if value not in arg:
                            try:
                                values.remove(value)  # List case
                            except AttributeError:
                                del values[value]  # Dict case
        # TODO: optimize
        if values:
            for value in values:
                self.validate(None, self.name, value)
        return values


class CollectionNotifier(list):
    """List that notifies the magics of its parent about modifications

    Parent must have the following methods:
        __insert__(self, name, index, value)
        __remove__(self, name, index, value)

    This inherits the list class and has all of the same methods

    Attributes
    ----------
    parent : object
        Parent class to notify
    name : string
        Name of this class for the parent's notification.
        This is so that notifications resemble __setattr__
    """
    def __init__(self, parent, name, items=None):
        self.parent = parent
        self.name = name
        list.__init__(self)
        if items:
            self.extend(items)

    def append(self, item):
        idx = len(self)
        self.parent.__insert__(self.name, idx, item)
        list.append(self, item)

    def extend(self, items):
        items = list(items)
        idx = len(self)
        for item in items:
            self.parent.__insert__(self.name, idx, item)
            idx += 1
        list.extend(self, items)

    def remove(self, item):
        idx = self.index(item)
        self.parent.__remove__(self.name, idx, item)
        list.remove(self, item)

    def pop(self, idx=None):
        if idx is None:
            idx = len(self)-1
        item = self[idx]
        self.parent.__remove__(self.name, idx, item)
        return list.pop(self, idx)

    # TODO: __setitem__


class Editable(Emitter, AtomicStruct):
    """Editable interface

    Attributes
    ----------
    keys : dict
        Mapping of restrictions
    accelerated : Bool
        If this object has a consistent structure, it can be built faster.
        define() will only get called the first time for all instances.

    Methods
    -------
    restrict
        Set restrictions on an attribute
    to_dict
        Generate a dict for this object
    to_json
        Generate a JSON string for this object

    Events
    ------
    set : (name, value)
        Fired before a restricted attribute is changed
    insert : (name, index, value)
        Fired before an item is inserted into a collection
    remove : (name, index, value)
        Fired before an item is removed from a collection
    invalid : (method, *args)
        Fired if an invalid value is passed. The rest of the event signature
        looks matches the method's arguments
    """
    # __metaclass__ = abc.ABCMeta
    accelerated = False

    def __init__(self, *args, **kwargs):
        reader = kwargs.pop('reader', None)
        if self.accelerated:
            AcceleratedAtomicStruct.initialize(self)
            if self._data is None:
                self.define(*args, **kwargs)
                AcceleratedAtomicStruct.freeze(self)
        else:
            AtomicStruct.__init__(self)
            self.define(*args, **kwargs)
            if self._data is None and self._fields:
                # Check if frozen and has things to freeze.
                self.freeze()
        if reader is not None:
            self.load(reader)

    def define(self, *args, **kwargs):
        """This provides the definition of the underlying struct. When
        overwritten, the editable will be automatically frozen.
        """
        pass

    @property
    def keys(self):
        """Map of restricted keys of this object. Keys are the names of the
        attributes. Values are Restriction instances.

        Returns
        -------
        keys : dict
        """
        try:
            return self._keys
        except AttributeError:
            from collections import OrderedDict
            self._keys = OrderedDict()
            return self._keys

    def __dir__(self):
        return self.__dict__.keys()+self.keys.keys()

    def restrict(self, name, validator=None, children=None, **kwargs):
        """Restrict an attribute. This adds the attribute to the key
        collection used to build textual representations.

        Parameters not passed will not be used to check validity.

        Parameters
        ----------
        name : string
            Name of the attribute
        min_value : optional
            Require value to be greater or equal to this value
        max_value : optional
            Require value to be less or equal to this value
        min_length : int, optional
            Require length of value to be greater or equal to this value
        max_length : int, optional
            Require length of value to be less or equal to this value
        validator : func(Editable, name, value), optional
            If set, this function gets passed the instance, name, and new
            value. This should raise a ValueError if the value should not
            be allowed.
        children : list of Restriction
            If not set, this will automatically grab the type of the
            currently set value
        """
        restriction = Restriction(name, **kwargs)
        if validator is not None:
            restriction.restrict(validator)
        if name is not SIMULATING_PLACEHOLDER:
            self.keys[name] = restriction
        return restriction
    attribute = restrict

    def int8(self, name, **kwargs):
        params = {'default': 0, 'min_value': -0x80, 'max_value': 0x7F, 'type': int}
        params.update(kwargs)
        field = AtomicStruct.int8(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def uint8(self, name, **kwargs):
        params = {'default': 0, 'min_value': 0, 'max_value': 0xFF, 'type': int}
        params.update(kwargs)
        field = AtomicStruct.uint8(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def int16(self, name, **kwargs):
        params = {'default': 0, 'min_value': -0x8000, 'max_value': 0x7FFF, 'type': int}
        params.update(kwargs)
        field = AtomicStruct.int16(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def uint16(self, name, **kwargs):
        params = {'default': 0, 'min_value': 0, 'max_value': 0xFFFF, 'type': int}
        params.update(kwargs)
        field = AtomicStruct.uint16(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def int32(self, name, **kwargs):
        params = {'default': 0, 'min_value': -0x80000000, 'max_value': 0x7FFFFFFF,
                  'type': int}
        params.update(kwargs)
        field = AtomicStruct.int32(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def uint32(self, name, **kwargs):
        params = {'default': 0, 'min_value': 0, 'max_value': 0xFFFFFFFF, 'type': int}
        params.update(kwargs)
        field = AtomicStruct.uint32(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def int64(self, name, **kwargs):
        params = {'default': 0, 'min_value': -0x8000000000000000,
                  'max_value': 0x7FFFFFFFFFFFFFFF, 'type': int}
        params.update(kwargs)
        field = AtomicStruct.int64(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def uint64(self, name, **kwargs):
        params = {'default': 0, 'min_value': 0,
                  'max_value': 0xFFFFFFFFFFFFFFFF, 'type': int}
        params.update(kwargs)
        field = AtomicStruct.uint64(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def float32(self, name, **kwargs):
        params = {'default': 0.0, 'type': float}
        params.update(kwargs)
        field = AtomicStruct.float32(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def float64(self, name, **kwargs):
        params = {'default': 0.0, 'type': float}
        params.update(kwargs)
        field = AtomicStruct.float64(self, name, **kwargs)
        self.restrict(name, **params)
        return field

    def struct(self, name, *args, **kwargs):
        field = AtomicStruct.struct(self, name, *args, **kwargs)
        self.restrict(name, **kwargs)
        return field

    def array(self, name,  *args, **kwargs):
        try:
            params = {'max_length': kwargs['length']}
            params.update(kwargs)
        except:
            params = kwargs
        field = AtomicStruct.array(self, name, *args, **kwargs)
        self.restrict(name, **params)
        return field

    def remove(self, name):
        self.keys.pop(name)
        return AtomicStruct.remove(self, name)

    def get_unrestricted(self, whitelist=None):
        """Get a list of all attributes that are not restricted

        This is a utility to verify all are restricted
        """
        keys = self.keys
        unrestricted = []
        if whitelist is None:
            whitelist = []
        for name, attr in self.__dict__.items():
            if hasattr(attr, '__call__'):
                continue
            if name in keys:
                continue
            if name[0] == '_':
                continue
            if name in whitelist:
                continue
            unrestricted.append(name)
        return unrestricted

    def __setattr__(self, name, value):
        if isinstance(value, list):
            value = CollectionNotifier(self, name, value)
        try:
            restriction = self.keys[name]
            restriction.name
        except:
            super(XEditable, self).__setattr__(name, value)
        else:
            try:
                restriction.validate(self, name, value)
            except ValueError:
                self.fire('invalid', ('set', name, value))
                raise
            try:
                old_value = getattr(self, name)
            except AttributeError:
                pass
            else:
                if name in self.__dict__:
                    AtomicStruct.__setattr__(self, name, value)
                elif self._data is None:
                    super(XEditable, self).__setattr__(name, value)
                else:
                    setattr(self._data, name, value)
                if old_value != value:
                    self.fire('set', (name, value))

    def __getattr__(self, name):
        if name not in self.__dict__ and name not in self.__class__.__dict__\
                and self._data is not None:
            return getattr(self._data, name)
        return object.__getattribute__(self, name)
        # super(XEditable, self).__getattr__(name)

    def __insert__(self, name, index, value):
        try:
            restriction = self.keys[name]
            restriction = restriction.child
        except:
            pass
        else:
            try:
                restriction.validate(self, name, value)
            except ValueError:
                self.fire('invalid', ('insert', name, index, value))
                raise
            self.fire('insert', (name, index, value))

    def __remove__(self, name, index, value):
        # TODO: validate lengths?
        self.fire('remove', (name, index, value))

    @staticmethod
    def fx_property(attr_name, shift=12):
        """Create a property that turns an int into a fixed point number

        Parameters
        ----------
        attr_name : str
            Name of underlying attribute
        shift : int
            Number of bits that go after the binary point
        """
        factor = float(1 << shift)

        def fget(self):
            return getattr(self, attr_name)/factor

        def fset(self, value):
            return setattr(self, attr_name, value*factor)

        return property(fget, fset)

    def checksum(self):
        """Returns a recursive weak_hash for this instance"""
        weak_hash = 0
        for key in self.keys:
            try:
                name = self.keys[key].name
            except:
                name = key
            value = getattr(self, name)
            for sub_key, sub_value in auto_iterate(value)[2]:
                try:
                    sub_value = sub_value.checksum()
                except AttributeError as err:
                    pass
                weak_hash += hash(sub_value)
        return weak_hash

    def to_dict(self):
        """Generates a dict recursively out of this instance

        Returns
        -------
        out : dict
        """
        out = {}
        for key in self.keys:
            try:
                name = self.keys[key].name
            except:
                name = key
            value = getattr(self, name)
            container, adder, iterator = auto_iterate(value)
            for sub_key, sub_value in iterator:
                try:
                    sub_value = sub_value.to_dict()
                except AttributeError as err:
                    pass
                container = adder(container, sub_key, sub_value)
            out[key] = container
        return out

    def from_dict(self, source, merge=True):
        """Loads a dict into this instance

        Parameters
        ----------
        source : dict.
            Dict to load in
        merge : Bool
            If true, this merges with the current data. Otherwise it
            resets missing fields

        Returns
        -------
        self : Editable
            For chaining
        """
        for key in self.keys:
            try:
                value = source[key]
            except KeyError:
                # TODO: handle reset if merge=False
                if not merge:
                    raise KeyError('Non-merge expected key: {0}'.format(key))
                continue
            old_value = getattr(self, key)
            try:
                old_value.from_dict(value, merge)
            except AttributeError:
                try:
                    value[:0]
                    if hasattr(value, 'strip'):
                        # String handling
                        raise TypeError
                except TypeError:
                    # TODO: handle dicts?
                    setattr(self, key, value)
                else:
                    i = -1
                    for i, subvalue in enumerate(value):
                        try:
                            try:
                                old_value[i].from_dict(subvalue, merge)
                            except AttributeError:
                                old_value[i] = subvalue
                        except IndexError:
                            old_value.append(subvalue)
                    i += 1
                    while len(old_value) > i:
                        old_value.pop(i)
        return self

    def to_json(self, **json_args):
        """Returns the JSON version of this instance

        Returns
        -------
        json_string : string
        """
        return json.dumps(self.to_dict(), **json_args)

    def print_restrictions(self, level=0):
        """Pretty-prints restrictions recursively"""
        prefix = '  '*level
        for key in self.keys:
            print('{prefix}{name}'.format(prefix=prefix, name=key))
            restriction = self.keys[key]
            try:
                restriction.name
            except:
                continue
            for restrict in ('min_value', 'max_value', 'min_length',
                             'max_length', 'validator'):
                value = getattr(restriction, restrict)
                if value is None:
                    continue
                if restrict == 'validator':
                    value = value.func_name
                print('{prefix}>> {restrict}="{value}"'.format(
                    prefix=prefix, restrict=restrict, value=value))
            for child in restriction.children:
                child.print_restrictions(level+1)

    def __repr__(self):
        return '<{cls}({value}) at {id}>'.format(cls=self.__class__.__name__,
                                                 value=self.to_dict(),
                                                 id=hex(id(self)))

    def _repr_pretty_(self, printer, cycle):
        if cycle:
            printer.text('{cls}(...)'.format(cls=self.__class__.__name__))
            return
        with printer.group(2, '{cls}('.format(cls=self.__class__.__name__),
                           ')'):
            printer.pretty(self.to_dict())
XEditable = Editable
