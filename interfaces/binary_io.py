from abc import ABCMeta, abstractmethod
from enum import ReprEnum
from struct import Struct


# TODO Find a better name
class StructModes(Struct, ReprEnum):
    """
    Enum of struct types
    """
    def __new__(cls, value: str) -> Struct:
        if len(value) != 1:
            raise TypeError('Struct reader\'s mode only has one argument')

        if not isinstance(value, str) or value not in ('b', 'B', 'h', 'H', 'i', 'I', 'q', 'Q'):
            raise TypeError('Struct reader\'s mode must be one of these characters: bBhHiIqQ')

        struct = Struct(value)
        member = Struct.__new__(cls)
        member._value_ = struct
        return member
    
    
    int8 = 'b'
    uint8 = 'B'
    int16 = 'h'
    uint16 = 'H'
    int32 = 'i'
    uint32 = 'I'
    int64 = 'q'
    uint64 = 'Q'


class IOHandler(metaclass=ABCMeta):
    """
    Interface for binary processes, this is here to replace the old
    BinaryIO from the old rawDB. Now this will be an interface and
    there will be a class FOR EACH type of data that can enter (i.e.
    one for files, one for str)
    """
    @abstractmethod
    def read(self, mode: StructModes) -> int:
        """
        Reads an integer from the binary buffer. Integer size is 
        defined by the specified mode.

        Args:
            mode (StructModes): Struct mode

        Returns:
            int: Read integer
        """
        pass


    @abstractmethod
    def read_bytes(self, length: int) -> bytes:
        """
        Reads raw data from the binary.

        Args:
            length (int): Data length

        Returns:
            bytes: The raw data
        """
        pass


    @abstractmethod
    def read_str(self) -> bytes:
        """
        Reads a string from the binary. Strings MUST end with the
        '\\0' character. 

        Returns:
            str: The string in decoded in UTF-8
        """
        pass

    
    @abstractmethod
    def write(self, mode: StructModes, value: int) -> None:
        """
        Writes an integer to the buffer. Integer size is defined by
        the specified mode. Replaces the bytes in place.

        Args:
            mode (StructModes): Struct mode
            value (int): Value to write
        """
        pass


    @abstractmethod
    def write_bytes(self, rawdata: bytes) -> None:
        """
        Writes rawdata to the buffer. Replaces the bytes 
        in place.

        Args:
            rawdata (bytes): Raw data
        """
        pass


    @abstractmethod
    def write_str(self, string: str) -> None:
        """
        Writes a string to the buffer. A '\\0' will be added at the
        end of the string, so you don't need to put it. The string
        must be in UTF-8 format. Replaces the bytes in place.

        Args:
            string (str): The string to write (without the ending '\\0')
        """
        pass


    @abstractmethod
    def align(self, byte_number: int, value: bytes = b'\x00'):
        """
        Aligns the position counter with the specified char.

        Args:
            byte_number (int): Alignment number
            value (bytes, optional): Alignment byte. Defaults to b'\x00'.
        """
        pass


    @abstractmethod
    def getvalue(self) -> bytes:
        """
        Returns the buffer's value. Avoid doing that on big buffers

        Returns:
            bytes: Buffer's value
        """
        pass

    
    @abstractmethod
    def seek(self, position: int) -> None:
        """
        Seeks to the specified position

        Args:
            position (int): New position
        """
        pass
