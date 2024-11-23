"""
AtomicStruct defines a structure for parsing raw data efficiently. The
substructures are compiled into a C-type equivalent.
"""
from abc import ABCMeta, abstractmethod
from enum import ReprEnum
from math import ceil
from typing import Any
from copy import copy

class AtomicError(RuntimeError):
    """
    Error raised when something happens during an AtomicField creation
    """
    pass


class FieldTypes(str, ReprEnum):
    """
    Enumeration of common types that are used in structs with 
    their name and size in bytes. Their format MUST BE str, int.
    Also the type name must be the enum element name

    Raises:
        TypeError: When the format is not str, int

    Returns:
        str: The data type's name
    """
    # Values must be tuple[str, int] corresponding to data's name and size
    def __new__(cls, *values) -> str:
        if len(values) < 2:
            raise TypeError('Field types must have at least 2 arguments, the data type name and its size in bytes')
        
        if not isinstance(values[1], int):
            raise TypeError('Field type size must be an int')

        value = str(values[0])
        member = str.__new__(cls, value)
        member._value_ = value
        return member
    

    @classmethod
    def from_type_name(cls, type_name: str) -> 'FieldTypes | None':
        return cls.__members__.get(type_name)


    def __init__(self, type_name: str, size: int, python_type: type, min: int | float = 0, max: int | float = 0):
        self.type_name = type_name
        self.size = size
        self.python_type = python_type
        # Min and max are defined only when it makes sense!
        self.min = min
        self.max = max


    char = 'char', 1, str
    bool = 'bool', 1, bool, False, True
    uint8_t = 'uint8_t', 1, int, 0, 0xFF
    uint16_t ='uint16_t', 2, int, 0, 0xFFFF
    uint32_t = 'uint32_t', 4, int, 0, 0xFFFFFFFF
    uint64_t = 'uint64_t', 8, int, 0, 0xFFFFFFFFFFFFFFFF
    int8_t = 'int8_t', 1, int, -0x80, 0x7F
    int16_t = 'int16_t', 2, int, -0x8000, 0x7FFF
    int32_t = 'int32_t', 4, int, -0x80000000, 0x7FFFFFFF
    int64_t = 'int64_t', 8, int, -0x8000000000000000, 0x7FFFFFFFFFFFFFFF
    double = 'double', 8, float, -1e37, 1e37 # Put before else it'll think I use the one of FieldTypes
    float = 'float', 4, float, -1e37, 1e37


class AtomicField(object, metaclass=ABCMeta):
    """
    Represents a field in a struct. It must have a size in bytes.
    """
    size: int
    bit_size: int

    def get_byte_size(self) -> int:
        """
        Returns the field's size in bytes

        Returns:
            int: Field's size in bytes
        """
        return self.size


    def get_bit_size(self) -> int:
        """
        Returns the field's size if in bits

        Returns:
            int: _description_
        """
        bit_size = 0
        if hasattr(self, 'bit_size'):
            bit_size = self.bit_size

        return bit_size
    

    @abstractmethod
    def describe(self, level: int) -> str:
        """
        String representation of the field

        Args:
            level (int): Indentation level

        Returns:
            str: Field's string representation
        """
        pass


class AtomicDataField(AtomicField):
    """
    Represents a data field in a struct. It has a name, a type, 
    can have a number of bits and a default value
    """
    name: str
    type_name: str
    width: int
    default: Any


    def __init__(self, name: str, _type: FieldTypes | str, width: int = 0, default: Any = None) -> None:
        """
        Represents a data field in a struct. It has a name, a type, 
        can have a number of bits and a default value

        Has the following description:

        [_type] [name]<:[width]> <// default:[default]> 

        Args:
            name (str): Field's name
            _type (FieldTypes | str): Field's type, can be custom (in that case set its size afterwards)
            width (int, optional): Field's size in bits. Defaults to 0.
            default (Any, optional): Field's default value. Defaults to None.
        """
        self.name = name

        if width == 0:
            if isinstance(_type, FieldTypes):
                self.size = _type.size
            else:
                self.size = 0 # No information so nothing!
        else:
            self.size = 0
            self.bit_size = width

        self.type_name = _type
        self.width = width
        self.default = default


    def describe(self, level: int = 0) -> str:
        indent = '\t' * level
        
        # Example uint32_t test:4;
        result = f'{indent:s}{self.type_name:s} {self.name:s}'

        if self.width > 0:
            result += f':{self.width:d}'
        result += ';'

        if self.default is not None:
            result += f' // default: {self.default}'

        return result 


class AtomicArrayField(AtomicDataField):
    """
    Represents an array field in a struct. It can be a type or a pointer. 
    """
    lengths: tuple[int, ...]
    

    def __init__(self, name: str, _type: FieldTypes | str, *, dimension: int = 1, lengths: tuple[int, ...] = (1,)) -> None:
        """
        Represents an array field of a data field in a struct. For an array of
        pointers, see AtomicArrayField.of_pointer

        Has the following description:

        [_type] [name][lengths[0]]...

        Args:
            name (str): Field's name
            _type (FieldTypes | str): Field's type, can be custom (in that case set its size afterwards)
            dimension (int, optional): Array's dimension. Defaults to 1.
            lengths (tuple[int, ...], optional): Array's length per dimension. Defaults to (1,).

        Raises:
            AtomicError: When the number of lengths does not match with the dimension
        """
        self.name = name
        self.type_name = _type
        self.width = dimension

        if dimension != 0 and len(lengths) != dimension:
            raise AtomicError(f'Length of array\'s length must be equal to the dimension ({len(lengths):d} != {dimension:d})')
        
        if isinstance(_type, FieldTypes):
            if dimension == 0: # Just a pointer
                self.size = 8 
            else: 
                self.size = _type.size
                for dim in range(0, dimension): # Matrix
                    self.size *= lengths[dim]
        else:
            self.size = 0; # No information so 0

        self.lengths = lengths


    # Because Python does not have multiple constructors
    @classmethod
    def of_pointer(cls, pointer: 'AtomicFieldPointer', *, dimension: int = 1, lengths: tuple[int, ...] = (1,)):
        """
        Represents an array field of a pointer field in a struct.

        Has the following description:

        [_type] *[name][lengths[0]]...

        Args:
            pointer (AtomicFieldPointer): Base pointer
            dimension (int, optional): Array's dimension. Defaults to 1.
            lengths (tuple[int, ...], optional): Array's length per dimension. Defaults to (1,).
        """
        array = cls(name=pointer.name, _type=pointer.type_name, dimension=dimension, lengths=lengths)
        array.size = 8
        if dimension != 0:
            for dim in range(0, dimension):
                array.size *= lengths[dim]

        return array


    def describe(self, level: int = 0) -> str:
        indent = '\t' * level
        result = f'{indent:s}{self.type_name:s} {self.name:s}'

        if self.width == 0:
            result += '[]'
        else:
            for dimension in range(0, self.width):
                result += f'[{self.lengths[dimension]}]'

        result += ';'
        return result


class AtomicFieldPointer(AtomicDataField):
    """
    Represents a pointer field in a struct
    """
    atomic_data_field: AtomicDataField

    @classmethod
    def of_type(cls, name: str, _type: FieldTypes | str) -> 'AtomicFieldPointer':
        """
        Creates a pointer from a type. Useful to create an array of pointers
        without having to create a data field before

        Args:
            name (str): Pointer's name
            _type (FieldTypes | str): Pointer's type
        """
        field = AtomicDataField(name=name, _type=_type)
        pointer = cls(atomic_data_field=field)
        return pointer
    

    def pointerize(self) -> 'AtomicFieldPointer':
        """
        Creates a pointer that points to `self` 
        """
        pointer2 = AtomicFieldPointer(atomic_data_field=self)
        return pointer2
    

    def __init__(self, atomic_data_field: AtomicDataField) -> None:
        """
        Represents a pointer field in a struct. Copied the field so do 
        not fear to have your field modified! Field can be a data field,
        an array field or a struct field

        Has the following description:

        [_type] *[name] ...

        or 

        [_type] (*[name])[lengths[0]]... (if AtomicArrayField)

        Args:
            atomic_data_field (AtomicDataField): Base data field
        """
        self.atomic_data_field = copy(atomic_data_field)

        if isinstance(atomic_data_field, AtomicArrayField):
            self.atomic_data_field.name = f'*({self.atomic_data_field.name:s})' 
        else:
            self.atomic_data_field.name = f'*{self.atomic_data_field.name:s}'
        
        # Repeating name and type name for data field normal process
        self.name = self.atomic_data_field.name
        self.type_name = self.atomic_data_field.type_name
        self.size = 8 # Size of a pointer


    def describe(self, level: int = 0) -> str:
        return self.atomic_data_field.describe(level=level)
    

class AtomicStructField(AtomicField):
    """
    Represents a struct, base field or embedded in a struct. 
    See AtomicStructBuilder to easily build a struct
    """
    name: str
    declared_struct_name: str
    fields: tuple[AtomicField, ...] # Immutable!
    is_extern: bool


    def __init__(self, name: str, fields: list[AtomicField], declared_struct_name: str = '') -> None:
        """
        Represents a struct, base field or embedded in a struct. Can be extern 
        with AtomicStructField.set_extern. See AtomicStructBuilder to easily build a struct.

        Has the following description:

        <extern> struct [name] {
            ...
        } [declared_struct_name]

        Args:
            name (str): Field's name
            fields (list[AtomicField]): Struct's fields
            declared_struct_name (str, optional): Declared struct's name. Defaults to ''.
        """
        self.name = name
        self.declared_struct_name = declared_struct_name
        self.fields = tuple(fields)
        self.is_extern = False

        self.size = 0
        self.bit_size = 0
        for field in fields:
            self.bit_size += field.get_bit_size()
            self.size += field.get_byte_size()
        self.size += ceil(self.bit_size / 8)


    def set_extern(self, status: bool = True) -> 'AtomicStructField':
        """
        Sets the struct as extern

        Args:
            status (bool, optional): True if needs to be extern. Defaults to True.
        """
        self.is_extern = status
        return self
    

    def describe(self, level: int = 0) -> str:
        indent = '\t' * level
        result = f'{indent:s}'

        if self.is_extern:
            result += 'extern '

        result += f'struct '
        
        if self.name != '':
            result += f'{self.name:s} '

        result += '{\n'
        fields_result = []
        for field in self.fields:
            fields_result.append(field.describe(level=level + 1))

        result += '\n'.join(fields_result)
        result += f'\n{indent:s}}}'

        if self.declared_struct_name != '':
            result += f' {self.declared_struct_name:s}'

        result += ';'
        return result


class AtomicStructBuilder(object):
    """
    A builder to quickly and easily build an AtomicStructField.
    """
    fields: dict[str, AtomicField]


    def __init__(self) -> None:
        """
        A builder to quickly and easily build an AtomicStructField.

        Here is an example of struct that you can create:

        >>> flag_struct = AtomicStructBuilder().add_field('enable', FieldTypes.uint8_t, width=2)\\
        >>> ...                                .add_field('type', FieldTypes.uint8_t, width=2)\\
        >>> ...                                .add_field('masked', FieldTypes.uint8_t, width=1)\\
        >>> ...                                .add_field('unused', FieldTypes.uint8_t, width=3)\\
        >>> ...                                .build('flags')
        >>> flag_struct.describe()
        >>> print(f'Struct size: {flag_struct.get_size():d} byte(s)')

        Output:
            struct flags {
                uint8_t enable:2;
                uint8_t type:2;
                uint8_t masked:1;
                uint8_t unused:3;
            };
            Struct size: 1 byte(s)
        """
        self.fields = {}


    def remove_field(self, name: str) -> None:
        """
        Removes the field described by its name

        Args:
            name (str): Field's name
        """
        if name in self.fields:
            del self.fields[name]


    def add_field(self, name: str, _type: FieldTypes, *, width: int = 0, default: Any = None) -> 'AtomicStructBuilder':
        """
        Adds a field to the struct.

        For example 

        >>> example_struct = AtomicStructBuilder().add_field('id', FieldTypes.uint64_t).build('example')
        >>> example_struct.describe()

        Output:
            struct example {
                uint64_t id;
            };

        Args:
            name (str): Field's name
            _type (FieldTypes): Field's type
            width (int, optional): Field's size in bits. Defaults to 0.
            default (Any, optional): Field's default value. Defaults to None.
        """
        self.fields[name] = AtomicDataField(name=name,
                                            _type=_type,
                                            width=width,
                                            default=default)
        return self


    def add_array(self, name: str, _type: FieldTypes, *, dimension: int = 1, lengths: tuple[int, ...] = (1,)) -> 'AtomicStructBuilder':
        """
        Adds an array to the struct. 

        For example:

        >>> example_struct = AtomicStructBuilder().add_array('matrix', FieldTypes.uint64_t, dimension=2, lengths=(10, 20,)).build('example')
        >>> example_struct.describe()

        Output:
            struct example {
                uint64_t matrix[10][20];
            };

        Args:
            name (str): Array's name
            _type (FieldTypes): Array's type
            dimension (int, optional): Array's dimension. Defaults to 1.
            lengths (tuple[int, ...], optional): Array's length per dimension. Defaults to (1,).
        """
        self.fields[name] = AtomicArrayField(name=name,
                                             _type=_type,
                                             dimension=dimension,
                                             lengths=lengths)
        return self


    def add_array_custom(self, name: str, type_name: str, *, dimension: int = 1, lengths: tuple[int, ...] = (1,)) -> 'AtomicStructBuilder':
        """
        Adds an array with a custom type to the struct. 

        For example:

        >>> example_struct = AtomicStructBuilder().add_array('matrix', "any", dimension=2, lengths=(10, 20,)).build('example')
        >>> example_struct.describe()

        Output:
            struct example {
                any matrix[10][20];
            };

        Args:
            name (str): Array's name
            type_name (str): Custom type's name
            dimension (int, optional): Array's dimension. Defaults to 1.
            lengths (tuple[int, ...], optional): Array's length per dimension. Defaults to (1,).
        """
        self.fields[name] = AtomicArrayField(name=name,
                                             _type=type_name,
                                             dimension=dimension,
                                             lengths=lengths)
        return self


    def add_pointer_field(self, name: str, _type: FieldTypes) -> 'AtomicStructBuilder':
        """
        Adds a pointer to the struct.

        For example:

        >>> example_struct = AtomicStructBuilder().add_pointer_field('name', FieldTypes.char).build('example')
        >>> example.describe()

        Output:
            struct example {
                char *name;
            };

        Args:
            name (str): Pointer's name
            _type (FieldTypes): Pointer's type
        """
        self.fields[name] = AtomicFieldPointer(AtomicDataField(name=name,
                                                               _type=_type))
        return self
    

    def add_pointer_custom(self, name: str, type_name: str) -> 'AtomicStructBuilder':
        """
        Adds a pointer to the struct.

        For example:

        >>> example_struct = AtomicStructBuilder().add_pointer_field('name', FieldTypes.char).build('example')
        >>> example.describe()

        Output:
            struct example {
                char *name;
            };

        Args:
            name (str): Pointer's name
            type_name (str): Pointer's type
        """
        self.fields[name] = AtomicFieldPointer(AtomicDataField(name=name,
                                                               _type=type_name))
        return self


    def add_pointer_of_array(self, name: str, _type: FieldTypes, *, dimension: int = 1, lengths: tuple[int, ...] = (1,)) -> 'AtomicStructBuilder':
        """
        Adds a pointer to an array.

        For example:

        >>> example_struct = AtomicStructBuilder().add_pointer_of_array('p_matrix', FieldTypes.uint64_t, dimension=2, lengths=(10, 20,)).build('example')
        >>> example_struct.describe()

        Output:
            struct example {
                uint64_t *(p_matrix)[10][20];
            };

        Args:
            name (str): Pointer's name
            _type (FieldTypes): Array's type
            dimension (int, optional): Array's dimension. Defaults to 1.
            lengths (tuple[int, ...], optional): Array's length per dimension. Defaults to (1,).
        """
        self.fields[name] = AtomicFieldPointer(AtomicArrayField(name=name,
                                                                _type=_type,
                                                                dimension=dimension,
                                                                lengths=lengths))
        return self
    

    def add_array_of_pointers(self, pointer: AtomicFieldPointer, *, dimension: int = 1, lengths: tuple[int, ...] = (1,)) -> 'AtomicStructBuilder':
        """
        Adds an array of pointers. The pointer can be created using AtomicFieldPointer.of_type

        For example: 

        >>> example_struct = AtomicStructBuilder().add_array_of_pointers(AtomicFieldPointer.of_type('ids', FieldTypes.uint64_t), dimension=1, lengths=(50,)).build('example')
        >>> example_struct.describe()

        Output:
            struct example {
                uint64_t *ids[50];
            };

        Args:
            pointer (AtomicFieldPointer): Base pointer
            dimension (int, optional): Array's dimension. Defaults to 1.
            lengths (tuple[int, ...], optional): Array's length per dimension. Defaults to (1,).
        """
        self.fields[pointer.name] = AtomicArrayField.of_pointer(pointer=pointer, 
                                                        dimension=dimension, 
                                                        lengths=lengths)
        return self

    
    def add_struct(self, struct: AtomicStructField, show_struct_name: bool, declared_struct_name: str = '') -> 'AtomicStructBuilder':
        """
        Adds a struct (embedded) to the struct. Must create a struct before.

        For example (using the flag struct shown in the class docstring):

        >>> example_struct1 = AtomicStructBuilder().add_struct(flag_struct, True, 'flags').build('example1')
        >>> example_struct2 = AtomicStructBuilder().add_struct(flag_struct, True).build('example2')
        >>> example_struct3 = AtomicStructBuilder().add_struct(flag_struct, False).build('example3')
        >>> example_struct1.describe()
        >>> example_struct2.describe()
        >>> example_struct3.describe()

        Output:
            struct example1 {
                struct flags {
                        uint8_t enable:2;
                        uint8_t type:2;
                        uint8_t masked:1;
                        uint8_t unused:3;
                } flags;
            };
            struct example2 {
                struct flags {
                        uint8_t enable:2;
                        uint8_t type:2;
                        uint8_t masked:1;
                        uint8_t unused:3;
                };
            };
            struct example3 {
                struct {
                        uint8_t enable:2;
                        uint8_t type:2;
                        uint8_t masked:1;
                        uint8_t unused:3;
                };
            };


        Args:
            struct (AtomicStructField): Struct to add
            show_struct_name (bool): True if struct's name needs to be displayed, False otherwise
            declared_struct_name (str): Struct's name if declared as a variable. Defaults to ''
        """
        copied_struct = copy(struct)
        copied_struct.declared_struct_name = declared_struct_name
        if not show_struct_name:
            copied_struct.name = ''

        self.fields[struct.name] = copied_struct
        return self
    

    def add_struct_field(self, name: str, struct: AtomicStructField) -> 'AtomicStructBuilder':
        """
        Adds a struct (not embedded) to the struct. Must create a struct before.

        For example (using the flag struct shown in the class docstring):

        >>> example_struct = AtomicStructBuilder().add_struct_field('flags', flag_struct).build('example')
        >>> example_struct.describe()

        Output:
            struct example {
                struct flags flags;
            };

        Args:
            name (str): Field's name
            struct (AtomicStructField): Struct to add
        """
        field = AtomicDataField(name=name,
                                _type=f'struct {struct.name:s}',
                                width=0,
                                default=None)
        field.size = struct.get_byte_size()
        self.fields[name] = field
        return self
    

    def add_struct_array(self, name: str, struct: AtomicStructField, dimension: int = 1, lengths: tuple[int, ...] = (1,)) -> 'AtomicStructBuilder':
        """
        Adds an array of struct. Must create a struct before.

        For example (using the flag struct shown in the class docstring):

        >>> example_struct = AtomicStructBuilder().add_struct_array('flags', flag_struct, dimension=1, lengths=(10,)).build('example')
        >>> example_struct.describe()

        Output:
            struct example {
                struct flags flags[10];
            };

        Args:
            name (str): Array's name
            struct (AtomicStructField): Struct to add
            dimension (int, optional): Array's dimension. Defaults to 1.
            lengths (tuple[int, ...], optional): Array's length per dimension. Defaults to (1,).
        """
        struct_array = AtomicArrayField(name=name,
                                        _type=f'struct {struct.name:s}',
                                        dimension=dimension,
                                        lengths=lengths)
        if dimension == 0: # Just a pointer
            struct_array.size = 8 
        else: 
            struct_array.size = struct.size
            for dim in range(0, dimension): # Matrix
                struct_array.size *= lengths[dim]
        self.fields[name] = struct_array
        return self
    

    def add_pointer_struct_field(self, name: str, struct: AtomicStructField) -> 'AtomicStructBuilder':
        """
        Adds a pointer of a struct. Must create a struct before.

        For example (using the flag struct shown in the class docstring):

        >>> example_struct = AtomicStructBuilder().add_pointer_struct_field('p_flags', flag_struct).build('example')
        >>> example_struct.describe()

        Output:
            struct example {
                struct flags *p_flags;
            };

        Args:
            name (str): Pointer's name
            struct (AtomicStructField): Struct to add
        """
        self.fields[name] = AtomicFieldPointer(AtomicDataField(name=name,
                                                               _type=f'struct {struct.name:s}',
                                                               width=0,
                                                               default=None))
        return self
    

    def add_custom(self, name: str, custom_type_name: str) -> 'AtomicStructBuilder':
        """
        Adds a custom field to the struct. This is useful when having classes.

        For example:

        >>> example_struct = AtomicStructBuilder().add_custom('custom', 'custom_type').build('example')

        Output:
            struct example {
                custom_type custom;
            };

        Args:
            name (str): Field's name
            custom_type_name (str): Custom type's name
        """
        self.fields[name] = AtomicDataField(name=name,
                                            _type=custom_type_name)
        return self

    
    def build(self, name: str, declared_struct_name: str = '') -> AtomicStructField:
        """
        Builds the struct.

        Args:
            name (str): Struct's name
            declared_struct_name (str, optional): Struct's name if declared as a variable . Defaults to ''.
        """
        return AtomicStructField(name=name, fields=list(self.fields.values()), declared_struct_name=declared_struct_name)
    