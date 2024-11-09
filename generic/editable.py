
from abc import ABCMeta, abstractmethod
import json
from collections import OrderedDict
from typing import Any, Callable

from rawdb.atomic import AtomicStructField
from rawdb.atomic.atomic_struct import AtomicArrayField, AtomicDataField, AtomicField, AtomicFieldPointer, AtomicStructBuilder, FieldTypes
from rawdb.event import INSERT_EVENT_NAME, INVALID_EVENT_NAME, REMOVE_EVENT_NAME, SET_EVENT_NAME
from rawdb.generic.restriction import Restriction

class Editable(object, metaclass=ABCMeta):
    """Editable interface

    Attributes
    ----------
    keys : dict
        Mapping of restrictions

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
    keys: dict[str, tuple[Any, Restriction | None]]

    def __init__(self, *args: Any) -> None:
        self.keys = OrderedDict()
        
        # Define struct using the abstract method
        builder = AtomicStructBuilder()
        self.define(builder, args)
        struct = builder.build('struct')

        # Add restrictions for each field
        self.__register_fields(fields=struct.fields)

    
    @classmethod
    def from_struct(cls, struct: AtomicStructField) -> 'Editable':
        """
        Creates a new Editable from a struct. Needs to declare this to 
        "bypass" the abstract method.

        Args:
            struct (AtomicStructField): Struct to use

        Returns:
            Editable: An editable of the same type than the calling class
        """
        editable = cls()
        editable.__register_fields(fields=struct.fields)

        return editable


    @abstractmethod
    def define(self, builder: AtomicStructBuilder, args: Any):
        """
        Method called during initialisation, used to define the underlying 
        struct and create restrictions. You can add other restrictions using
        the `restrict()` method. This will define the class' structure, YOU
        MUST DECLARE IN THIS METHOD every class attribute.

        An example would be:
        >>> def define(self, builder):
        >>> ... builder.add_field('id', FieldTypes.uint64_t)\\
        >>> ...        .add_pointer_field('name', FieldTypes.char)\\
        >>> ...        .add_field('age', FieldTypes.uint8_t)

        Note that adding a string can limit restrictions. In the example,
        the char* means that there is no restriction on the string size. If 
        you want to directly restrict the size, you can either add an array:
        (here an array of 9 chars (DO NOT FORGET THE '\\0'!))
        >>> builder.add_array('name', FieldTypes.char, lengths=(10,))

        Or restrict later with:
        >>> example.restrict('name', 'name_len', lambda name: len(name) < 10)

        If you need to add a custom object, you can use `add_custom()`, type
        and length will not be checked (default value will be 0)

        Args:
            builder (AtomicStructBuilder): Struct builder
            args (Any): Specific argument to pass to the subclass implementation

        Returns:
            None: Returns nothing, just add to the builder
        """
        pass


    def __register_fields(self, fields: tuple[AtomicField, ...]):
        for field in fields:
            # Check if field is a struct. In that case, we create a new Editable
            if isinstance(field, AtomicStructField):
                sub_struct = Editable.from_struct(field)
                self.keys[field.name] = (sub_struct, None)

            # If field is an array, then create a list and restrict length
            elif isinstance(field, AtomicArrayField):
                self.__register_array_field(array_field=field)

            # If field is a pointer, do like for an array BUT do not restrict the length
            elif isinstance(field, AtomicFieldPointer):
                self.__register_pointer_field(pfield=field)

            # Else just treat it like a field:
            elif isinstance(field, AtomicDataField):
                self.__register_data_field(data_field=field)


    def __register_array_field(self, array_field: AtomicArrayField):
        # If type is a char, then dimension 1 is a string, dimension n > 1 is a list... of string
        # Dimension 0 is an unrestricted string
        field = FieldTypes.from_type_name(array_field.type_name)
        if field is not None:
            field_type = field.python_type
            if field.python_type == str:
                value = '\0'
            elif field.python_type == bool:
                value = False
            else:
                value = field.min
            
        else:
            field_type = None
            value = None

        restriction = Restriction(array_field.name)

        # If no dimension, then like a pointer
        if array_field.width == 0:
            if field_type == str:
                restriction.restrict('field_type', lambda value: isinstance(value, str))
            if field_type is not None:
                restriction.restrict('field_type', lambda arr: all(isinstance(value, field_type) for value in arr))
                value = [value]

        # One dimension, then has a size
        elif array_field.width == 1:
            if field_type == str:
                # Remember that the last char of a string is always '\0'
                restriction.restrict('field_type', lambda value: isinstance(value, str))
                restriction.restrict('field_size', lambda value: len(value) == array_field.lengths[0] - 1)
                value = '\0' * (array_field.lengths[0] - 1)
            else:
                if field_type is not None:
                    restriction.restrict('field_type', lambda arr: all(isinstance(value, field_type) for value in arr))
                value = [value for _ in range(0, array_field.lengths[0])]
                restriction.restrict('field_size', lambda value: len(value) == array_field.lengths[0])
            
        
        else:
            # TODO If more than 1 dimension, add check for every elements
            if field_type == str:
                value = '\0' * (array_field.lengths[0] - 1)
                value = self.create_ndarray(list(array_field.lengths[1:]), value)
            else:
                value = self.create_ndarray(list(array_field.lengths), value)
            
            # Just add restriction to the first step
            restriction.restrict('field_type', lambda value: isinstance(value, list))
            restriction.restrict('field_size', lambda value: len(value) == array_field.lengths[-1])

        self.keys[array_field.name] = (value, restriction)


    def __register_pointer_field(self, pfield: AtomicFieldPointer):
        restriction = Restriction(pfield.name)
        value = []
        field = FieldTypes.from_type_name(pfield.type_name)
        if field is not None:
            field_type = field.python_type
        else:
            field_type = None

        if field_type == str:
            restriction.restrict('field_type', lambda value: isinstance(value, str))
            value = ''
        elif field_type is not None:
            restriction.restrict('field_type', lambda arr: all(isinstance(value, field_type) for value in arr))

        self.keys[pfield.name[1:]] = (value, restriction)


    def __register_data_field(self, data_field: AtomicDataField) -> None:
        restriction = Restriction(data_field.name)
        # If type is a char, then limit to one letter
        if data_field.type_name == 'char':
            restriction.restrict('field_type', lambda value: isinstance(value, str))
            restriction.restrict('field_size', lambda value: len(value) == 1)
            value = '\0'

        # If it is a bool, then limit to bool type
        elif data_field.type_name == 'bool':
            restriction.restrict('field_type', lambda value: isinstance(value, bool))
            value = False

        # Else search for it and get the min and max value
        else:
            field_type = FieldTypes.from_type_name(data_field.type_name)
            value = 0

            if field_type is not None:
                python_type = field_type.python_type
                min_value = field_type.min
                max_value = field_type.max

                restriction.restrict('field_type', lambda value: isinstance(value, python_type))
                restriction.restrict('field_value', lambda value: min_value <= value <= max_value)

        if data_field.default is not None:
            value = data_field.default

        self.keys[data_field.name] = (value, restriction)


    def __getattr__(self, name: str) -> Any | None:
        """
        Gets the attribute that is in the keys dict, or raises an error

        Args:
            name (str): Attribute name

        Returns:
            Any: Stored value
        """
        # Returns the dict
        if name == 'keys':
            return object.__getattribute__(self, name)

        # Else return the field in the dict
        if name in self.keys:
            return self.keys[name][0]

        raise AttributeError(f'\'{type(self).__name__:s}\' object has no attribute {name:s}')


    def __setattr__(self, name: str, value: Any) -> None:
        # Create the dict only once!
        if name == 'keys':
            try:
                object.__getattribute__(self, name)
            except:
                # If object does not exist, then not instantiated
                object.__setattr__(self, name, value)

        # Else test if is in the dict
        elif name in self.keys:
            restriction = self.keys[name][1]
            if restriction != None:
                # Do not catch error here, good luck in front end (TODO Verify if need to catch haha)
                restriction.validate(value=value)

                # If everything is good then change value
                self.keys[name] = (value, restriction)
            
            self.validate()

        else:
            raise AttributeError(f'\'{type(self).__name__:s}\' object has no attribute {name:s}')
        

    def restrict(self, field_name: str, restriction_name: str, validator: Callable[[Any], bool]):
        """
        Adds a restriction to an existing field. Does nothing if
        the field does not exist or if the field is an Editable.

        Args:
            field_name (str): Field's name
            restriction_name (str): Restriction's name
            validator (Callable[[Any], bool]): Validator function
        """
        if field_name in self.keys:
            (_, restriction) = self.keys[field_name]
            if restriction is not None:
                restriction.restrict(name=restriction_name, validator=validator)

    
    def validate(self):
        for (value, restriction) in self.keys.values():
            if restriction is not None:
                restriction.validate(value=value)
            else:
                # In that case value is an Editable
                if isinstance(value, Editable):
                    value.validate()                


    @staticmethod
    def create_ndarray(lengths: list[int], value: Any) -> list[Any]:
        if len(lengths) == 1:
            return [value] * lengths[0]
        else:
            return [Editable.create_ndarray(lengths[:-1], value) for _ in range(0, lengths[-1])]


#     @staticmethod
#     def fx_property(attr_name, shift=12):
#         """Create a property that turns an int into a fixed point number

#         Parameters
#         ----------
#         attr_name : str
#             Name of underlying attribute
#         shift : int
#             Number of bits that go after the binary point
#         """
#         factor = float(1 << shift)

#         def fget(self):
#             return getattr(self, attr_name)/factor

#         def fset(self, value):
#             return setattr(self, attr_name, value*factor)

#         return property(fget, fset)

#     def checksum(self):
#         """Returns a recursive weak_hash for this instance"""
#         weak_hash = 0
#         for key in self.keys:
#             try:
#                 name = self.keys[key].name
#             except:
#                 name = key
#             value = getattr(self, name)
#             for sub_key, sub_value in auto_iterate(value)[2]:
#                 try:
#                     sub_value = sub_value.checksum()
#                 except AttributeError as err:
#                     pass
#                 weak_hash += hash(sub_value)
#         return weak_hash

#     def to_dict(self):
#         """Generates a dict recursively out of this instance

#         Returns
#         -------
#         out : dict
#         """
#         out = {}
#         for key in self.keys:
#             try:
#                 name = self.keys[key].name
#             except:
#                 name = key
#             value = getattr(self, name)
#             container, adder, iterator = auto_iterate(value)
#             for sub_key, sub_value in iterator:
#                 try:
#                     sub_value = sub_value.to_dict()
#                 except AttributeError as err:
#                     pass
#                 container = adder(container, sub_key, sub_value)
#             out[key] = container
#         return out

#     def from_dict(self, source, merge=True):
#         """Loads a dict into this instance

#         Parameters
#         ----------
#         source : dict.
#             Dict to load in
#         merge : Bool
#             If true, this merges with the current data. Otherwise it
#             resets missing fields

#         Returns
#         -------
#         self : Editable
#             For chaining
#         """
#         for key in self.keys:
#             try:
#                 value = source[key]
#             except KeyError:
#                 # TODO: handle reset if merge=False
#                 if not merge:
#                     raise KeyError('Non-merge expected key: {0}'.format(key))
#                 continue
#             old_value = getattr(self, key)
#             try:
#                 old_value.from_dict(value, merge)
#             except AttributeError:
#                 try:
#                     value[:0]
#                     if hasattr(value, 'strip'):
#                         # String handling
#                         raise TypeError
#                 except TypeError:
#                     # TODO: handle dicts?
#                     setattr(self, key, value)
#                 else:
#                     i = -1
#                     for i, subvalue in enumerate(value):
#                         try:
#                             try:
#                                 old_value[i].from_dict(subvalue, merge)
#                             except AttributeError:
#                                 old_value[i] = subvalue
#                         except IndexError:
#                             old_value.append(subvalue)
#                     i += 1
#                     while len(old_value) > i:
#                         old_value.pop(i)
#         return self

#     def to_json(self, **json_args):
#         """Returns the JSON version of this instance

#         Returns
#         -------
#         json_string : string
#         """
#         return json.dumps(self.to_dict(), **json_args)

#     def print_restrictions(self, level=0):
#         """Pretty-prints restrictions recursively"""
#         prefix = '  '*level
#         for key in self.keys:
#             print('{prefix}{name}'.format(prefix=prefix, name=key))
#             restriction = self.keys[key]
#             try:
#                 restriction.name
#             except:
#                 continue
#             for restrict in ('min_value', 'max_value', 'min_length',
#                              'max_length', 'validator'):
#                 value = getattr(restriction, restrict)
#                 if value is None:
#                     continue
#                 if restrict == 'validator':
#                     value = value.func_name
#                 print('{prefix}>> {restrict}="{value}"'.format(
#                     prefix=prefix, restrict=restrict, value=value))
#             for child in restriction.children:
#                 child.print_restrictions(level+1)

#     def __repr__(self):
#         return '<{cls}({value}) at {id}>'.format(cls=self.__class__.__name__,
#                                                  value=self.to_dict(),
#                                                  id=hex(id(self)))

#     def _repr_pretty_(self, printer, cycle):
#         if cycle:
#             printer.text('{cls}(...)'.format(cls=self.__class__.__name__))
#             return
#         with printer.group(2, '{cls}('.format(cls=self.__class__.__name__),
#                            ')'):
#             printer.pretty(self.to_dict())
# XEditable = Editable
