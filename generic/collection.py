import ctypes
from turtle import width
from typing import Any

from cycler import V
from numpy import resize
from rawdb.atomic.atomic_struct import AtomicStructBuilder, FieldTypes
from rawdb.generic.editable import Editable
from rawdb.generic.restriction import Restriction


# TODO Add type hints
class Collection2d(Editable):
    entries: list[Any]
    width: int
    height: int

    def __init__(self, _type: FieldTypes, width: int, height: int) -> None:
        """
        Creates a 2D collection (2D matrix) of the specified type, width and height.
        It is implemented to only verify values when you access the object like a list.
        The list's key is a tuple the x index and y index. 

        For example: 
        >>> example_matrix = Collection2d(FieldTypes.uint8_t, 3, 4)
        >>> example_matrix[1, 1] = 2
        >>> print(example_matrix)

        Output: 
            [[0, 0, 0], [0, 2, 0], [0, 0, 0], [0, 0, 0]]
            
        Args:
            _type (FieldTypes): Matrix's type
            width (int): Matrix's width
            height (int): Matrix's height
        """
        super().__init__(_type, width, height)

        # Restrict further the list
        if _type != FieldTypes.char:
            # Type
            self.restrict('entries', 'items_type', lambda array: all(
                all(isinstance(value, _type.python_type) for value in subarray) for subarray in array)
            )
            # Value
            self.restrict('entries', 'items_value', lambda array: all(
                all(_type.min <= value <= _type.max for value in subarray) for subarray in array)
            )
            # Size
            self.restrict('entries', 'subarray_size', lambda array: all(
                len(subarray) == width for subarray in array)
            )

        else:
            # Type
            self.restrict('entries', 'items_type', lambda array: all(isinstance(value, str) for value in array))
            # Size (char* finishes by '\0')
            self.restrict('entries', 'items_type', lambda array: all(len(value) == width - 1 for value in array))

        self.validate()


    def define(self, builder: AtomicStructBuilder, args: tuple[FieldTypes, int, int]) -> None:
        builder.add_array('entries', args[0], dimension=2, lengths=(args[1], args[2]))


    def __getitem__(self, key: tuple[int, int]):
        return self.entries[key[0]][key[1]]
    

    def __setitem__(self, key: tuple[int, int], value: Any):
        sublist = self.entries[key[0]]
        if isinstance(sublist, str):
            strlist = list(sublist)
            strlist[key[1]] = value
            self.entries[key[0]] = "".join(strlist)
        else:
            sublist[key[1]] = value
        self.validate()


    def fill(self, value: Any, x: int, y: int, width: int, height: int):
        """
        Sets a region to a particular value

        Args:
            value (Any): Region's value
            x (int): Start x index
            y (int): Start y index
            width (int): Region's width
            height (int): Region's height
        """
        for sub_y in range(y, y+height):
            for sub_x in range(x, x+width):
                self[sub_x, sub_y] = value


    def fill_rect(self, value: Any, x1: int, y1: int, x2: int, y2: int):
        """
        Similar to `fill()` but using indexes

        Args:
            value (Any): Region's value
            x1 (int): Start x index
            y1 (int): Start y index
            x2 (int): End x index
            x2 (int): End y index
        """
        self.fill(value, x1, y1, x2-x1, y2-y1)

    
    def __str__(self) -> str:
        return self.entries.__str__()


class SizedCollection(Editable):
    entries: str | list[Any]
    resizable: bool

    def __init__(self, _type: FieldTypes, length: int, resizable: bool = True) -> None:
        """
        Creates a new 1D Collection with a dynamic size (yes, it is possible with AtomicStructs!).
        It is implemented to verify values when you access this object like a list.
        The list key is simply an integer.

        It is possible to resize the list with `resize`, where you give the new length, or 
        with `append`/`pop` to add/remove one item.

        For example:
        >>> example_array = SizedCollection(FieldTypes.uint32_t, 5)
        >>> for i in range(0, 5):
        >>> ... example_array[i] = i
        >>> example_array.append(5)
        >>> print(example_array)
        Args:
            _type (FieldTypes): _description_
            length (int): _description_
            resizable (bool, optional): _description_. Defaults to True.
        """
        super().__init__(_type, resizable)

        # Add size restriction
        restriction = self.keys['entries'][1]
        if isinstance(restriction, Restriction):
            if _type == FieldTypes.char:
                self.entries = '\0' * (length - 1)
                restriction.restrict('field_size', lambda string: len(string) == length - 1)
            else:
                self.entries = [_type.min] * length
                restriction.restrict('field_size', lambda string: len(string) == length)


    def define(self, builder: AtomicStructBuilder, args: tuple[FieldTypes, bool]) -> None:
        builder.add_pointer_field('entries', args[0])
        builder.add_field('resizable', FieldTypes.bool, default=args[1])


    def resize(self, length: int) -> None:
        """
        Resizes the array, if the new length is greater than the old one, 
        the first value will be copied to these new indexes. 

        Args:
            length (int): Array's new length
        """
        if self.resizable:
            # No need to validate at the end since resizing respects the new restriction
            if isinstance(self.entries, str):
                old_length = len(self.entries) + 1
            else:
                old_length = len(self.entries)

            # If already the good length, do nothing
            if length != old_length:
                # Change restriction to the new length
                restriction = self.keys['entries'][1]
                if isinstance(restriction, Restriction):
                    if isinstance(self.entries, str):
                        restriction.restrict('field_size', lambda array: len(array) == length - 1)
                    else:
                        restriction.restrict('field_size', lambda array: len(array) == length)

                    # Change array size
                    if length > old_length:
                        # If bigger, then add new elements of the array (add the first element as value)
                        value = self.entries[0]
                        if isinstance(self.entries, str):
                            self.entries += value * (length - old_length)
                        else:
                            self.entries += [value] * (length - old_length)
                    else:
                        # If smaller, then remove elements of the array
                        if isinstance(self.entries, str):
                            self.entries = self.entries[:length - 1]
                        else:
                            self.entries = self.entries[:length]


    def append(self, value: Any) -> None:
        if self.resizable:
            if isinstance(self.entries, str):
                length = len(self.entries) + 1
            else: 
                length = len(self.entries)

            self.resize(length + 1)

            if isinstance(self.entries, str):
                self.__setitem__(length - 1, value)
            else:
                self.__setitem__(length, value)


    def pop(self) -> Any:
        value = None
        if self.resizable:
            value = self.entries[-1]
            if isinstance(self.entries, str):
                length = len(self.entries) + 1
            else: 
                length = len(self.entries)
            
            self.resize(length - 1)
        
        return value


    def __getitem__(self, key: int) -> Any:
        return self.entries[key]


    def __setitem__(self, key: int, value: Any) -> None:
        if isinstance(self.entries, str):
            strlist = list(self.entries)
            strlist[key] = value
            self.entries = "".join(strlist)
        else:
            self.entries[key] = value
        self.validate()


    def __len__(self):
        return len(self.entries)


    def __iter__(self):
        return iter(self.entries)

    
    def __str__(self) -> str:
        return self.entries.__str__()