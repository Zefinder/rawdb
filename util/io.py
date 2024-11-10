from struct import calcsize
from rawdb.interfaces.binary_io import IOHandler, StructModes

class IOFileHandler(IOHandler):
    filename: str
    readable: bool
    writable: bool
    position: int

    def __init__(self, filename: str, mode: str = 'rw') -> None:
        """
        Creates a new IOHandler with a file. The mode is either 
        'r', 'w' or 'rw' (for read, write or read/write). The position
        is shared for reads and writes, means that reading 1 byte at 
        position 0 will write at position 1 (quite normal, but python r+
        does not follow this.).

        Args:
            filename (str): File name
            mode (str, optional): Opening mode. Defaults to 'rw'.
        """
        self.readable = 'r' in mode
        self.writable = 'w' in mode
        self.filename = filename
        self.position = 0


    def read(self, mode: StructModes) -> int:
        if self.readable:
            with open(self.filename, 'br') as file:
                # Seek to position
                file.seek(self.position)

                struct_len = calcsize(mode.format)
                self.position += struct_len
                return mode.unpack(file.read(struct_len))[0]

        # Default value is 0 (char \0)
        return 0

    def read_bytes(self) -> bytes:
        if self.readable:
            with open(self.filename, 'br') as file:
                # Seek to position
                file.seek(self.position)

                result = b''
                read_char = file.read(1)
                self.position += 1

                while read_char != b'\0':
                    result += read_char
                    read_char = file.read(1)
                    self.position += 1

                return result
            
        # Default value is b'\0'
        return b'\0'


    def read_str(self) -> str:
        if self.readable:
            with open(self.filename, 'br') as file:
                # Seek to position
                file.seek(self.position)

                # Search for the \0 character
                old_position = self.position
                read_char = b''
                chars_read = 0
                while read_char != b'\0':
                    read_char = file.read(1)
                    chars_read += 1

                # Return to old position and read the whole bytes
                file.seek(old_position)
                bytes_results = file.read(chars_read)
                self.position += chars_read

                # Return the decoded string MINUS the \0 character
                return bytes_results.decode('utf-8')[:-1]
        
        # Default value is '\0'
        return '\0'


    def transform_data(self, value: bytes) -> bytes:
        # Get value current value
        data = self.getvalue()

        # Save before position changing
        first_data = data[:self.position]

        # If position + length is greater or equal to the file length, no work to do
        if self.position + len(value) >= len(data):
            result = first_data + value
        else:
            last_data = data[self.position + len(value):]
            result = first_data + value + last_data
        
        return result


    def write(self, mode: StructModes, value: int) -> None:
        if self.writable:
            new_data = self.transform_data(mode.pack(value))
            with open(self.filename, 'bw') as file:
                file.write(new_data)
                self.position += calcsize(mode.format)


    def write_bytes(self, string: bytes) -> None:
        if self.writable:
            # Search for a \0, if not present then add it at the end
            null_index = string.find(b'\0')
            if null_index == -1:
                null_index = len(string)
                string += b'\0'
            
            new_data = self.transform_data(string)
            with open(self.filename, 'bw') as file:
                file.write(new_data)
                self.position += len(string)


    def write_str(self, string: str) -> None:
        if self.writable:
            # Search for a \0, if not present then add it at the end
            null_index = string.find('\0')
            if null_index == -1:
                null_index = len(string)
                string += '\0'

            bytes_string = string.encode('utf-8')

            new_data = self.transform_data(bytes_string)
            with open(self.filename, 'bw') as file:
                file.write(new_data)
                self.position += len(bytes_string)

    
    def align(self, byte_number: int, value: bytes = b'\x00') -> None:
        if self.writable:
            # Check if value is a single byte
            if len(value) > 1:
                value = value[:1]

            bytes_to_write = value * (self.position % byte_number)
            new_data = self.transform_data(bytes_to_write)
            with open(self.filename, 'bw') as file:
                file.write(new_data)
                self.position += len(bytes_to_write)


    def getvalue(self) -> bytes:
        if self.readable:
            with open(self.filename, 'br') as file:
                return file.read()

        # Default value is b'\0'
        return b'\0'
    

    def seek(self, position: int) -> None:
        self.position = position


class IOBytesHandler(IOHandler):
    content: bytes
    position: int

    def __init__(self, filename: str = '') -> None:
        """
        Creates a new string IOHandler with a file. The mode is either 
        'r', 'w' or 'rw' (for read, write or read/write). The position
        is shared for reads and writes, means that reading 1 byte at 
        position 0 will write at position 1 (quite normal, but python r+
        does not follow this.).

        Note that for the string version, there does not need an access mode

        Args:
            filename (str): File name. Defaults to ''
        """
        self.content = b''
        # If empty filename, then no load, just an empty string
        if filename != '':
            with open(filename, 'br') as file:
                self.content = file.read()

        self.position = 0


    def read(self, mode: StructModes) -> int:
        struct_len = calcsize(mode.format)
        result = mode.unpack_from(self.content, self.position)[0]
        self.position += struct_len
        
        return result
    

    def read_bytes(self) -> bytes:
        result = b''
        null_index = self.content.find(b'\0', self.position)
        result = self.content[self.position:null_index]
        self.position = null_index

        return result


    def read_str(self) -> str:
        # Search for the \0 character
        null_index = self.content.find(b'\0', self.position)
        result = self.content[self.position:null_index]
        self.position = null_index

        # Return the decoded string MINUS the \0 character
        return result.decode('utf-8')[:-1]


    def transform_data(self, value: bytes) -> bytes:
        # Save before position changing
        first_data = self.content[:self.position]

        # If position + length is greater or equal to the file length, no work to do
        if self.position + len(value) >= len(self.content):
            result = first_data + value
        else:
            last_data = self.content[self.position + len(value):]
            result = first_data + value + last_data
        
        return result


    def write(self, mode: StructModes, value: int) -> None:
        self.content = self.transform_data(mode.pack(value))
        self.position += calcsize(mode.format)


    def write_bytes(self, string: bytes) -> None:
        # Search for a \0, if not present then add it at the end
        null_index = string.find(b'\0')
        if null_index == -1:
            null_index = len(string)
            string += b'\0'
        
        self.content = self.transform_data(string)
        self.position += len(string)


    def write_str(self, string: str) -> None:
        # Search for a \0, if not present then add it at the end
        null_index = string.find('\0')
        if null_index == -1:
            null_index = len(string)
            string += '\0'

        bytes_string = string.encode('utf-8')

        self.content = self.transform_data(bytes_string)
        self.position += len(bytes_string)

    
    def align(self, byte_number: int, value: bytes = b'\x00') -> None:
        # Check if value is a single byte
        if len(value) > 1:
            value = value[:1]

        bytes_to_write = value * (self.position % byte_number)
        self.content = self.transform_data(bytes_to_write)
        self.position += len(bytes_to_write)


    def getvalue(self) -> bytes:
        return self.content
    

    def seek(self, position: int) -> None:
        self.position = position

