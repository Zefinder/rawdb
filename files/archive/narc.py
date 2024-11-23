import os
import shutil
from typing import Any
from rawdb.atomic.atomic_struct import AtomicStructBuilder, FieldTypes
from rawdb.files.extension_enum import ExtensionEnum
from rawdb.files.generic_header import GenericHeader
from rawdb.generic.editable import Editable
from rawdb.interfaces.binary_io import IOHandler, StructModes
from rawdb.interfaces.exportable import Exportable
from rawdb.interfaces.loadable import Loadable
from rawdb.interfaces.savable import Savable
from rawdb.util.io import IOFileHandler


class BTAF(Editable, Loadable, Savable):
    magic_id: int # uint32
    section_size: int # uint32
    file_number: int # uint32
    current_offset: int # uint32
    files_offset: list[list[int]] # uint32

    def __init__(self) -> None:
        """
        First subsection of the NARC
        """
        super().__init__()
        self.magic_id = int.from_bytes(b'BTAF', 'little')
        self.section_size = 12 # magic + section size + file number
        self.file_number = 0
        self.current_offset = 0
    

    def define(self, builder: AtomicStructBuilder, *_: Any):
        builder.add_field('magic_id', FieldTypes.uint32_t)\
               .add_field('section_size', FieldTypes.uint32_t)\
               .add_field('file_number', FieldTypes.uint32_t)\
               .add_field('current_offset', FieldTypes.uint32_t)\
               .add_pointer_of_array('files_offset', FieldTypes.uint32_t, dimension=1, lengths=(2, ))
        
    
    def add_file(self, size: int, offset: int):
        """
        Adds a file to the BTAF: File Allocation Table

        Args:
            size (int): File size
            offset (int): Start offset
        """
        self.section_size += 8 # Adding 4 bytes for start offset, and 4 for end offset
        self.file_number += 1
        self.files_offset.append([self.current_offset + offset, self.current_offset + offset + size])
        self.current_offset += offset + size
    

    def load(self, reader: IOHandler) -> None:
        self.magic_id = reader.read(StructModes.uint32)
        self.section_size = reader.read(StructModes.uint32)
        self.file_number = reader.read(StructModes.uint32)
        self.files_offset = []
        for _ in range(0, self.file_number):
            start_offset = reader.read(StructModes.uint32)
            end_offset = reader.read(StructModes.uint32)
            self.files_offset.append([start_offset, end_offset])
            self.current_offset = end_offset
    

    def save(self, writer: IOHandler) -> IOHandler:
        writer.write(StructModes.uint32, self.magic_id)
        writer.write(StructModes.uint32, self.section_size)
        writer.write(StructModes.uint32, self.file_number)
        for index in range(0, self.file_number):
            start_offset, end_offset = self.files_offset[index]
            writer.write(StructModes.uint32, start_offset)
            writer.write(StructModes.uint32, end_offset)

        return writer


class BTNF(Editable, Loadable, Savable):
    magic_id: int # uint32
    section_size: int # uint32
    main_table: list[tuple[int, int, int]] # (uint32, uint16, uint16)
    has_nametable: bool
    sub_tables: dict[int, list[tuple[int, str] | tuple[int, str, int]]] # (uint8, char* without \0) pr (uint8, char* without \0, uint16)


    def __init__(self) -> None:
        """
        Second subsection of the NARC: File Name Table
        """
        super().__init__()
        self.magic_id = int.from_bytes(b'BTNF', 'little')
        self.section_size = 16
        self.main_table = [(4, 0, 1)]
        self.sub_tables = {0: []}


    def define(self, builder: AtomicStructBuilder, *_: Any) -> None:
        builder.add_field('magic_id', FieldTypes.uint32_t)\
               .add_field('section_size', FieldTypes.uint32_t)\
               .add_pointer_custom('main_table', 'dir_table')\
               .add_field('has_nametable', FieldTypes.bool, default=False)\
               .add_field('file_id', FieldTypes.uint32_t, default=0)\
               .add_pointer_custom('sub_tables', 'sub_table')
        
    
    def use_nametable(self, value: bool = True, /) -> None:
        """
        Sets the use of a nametable

        Args:
            value (bool, optional): True if there is a nametable, False otherwise. Defaults to True.
        """
        self.has_nametable = value


    def add_directory(self, subtable_offset: int, first_file_id: int, parent_id: int, directory_name: str = '', directory_id: int = 0) -> None:
        """
        Adds a directory to the BTNF

        Args:
            subtable_offset (int): Offset of the subtable for this subdirectory
            first_file_id (int): First file id
            parent_id (int): Parent's directory id
            directory_name (str, optional): Directory's name (if nametable). Defaults to ''.
            directory_id (int, optional): Directory's id (if nametable). Defaults to 0.
        """
        # Add to main table and create new subtable
        self.main_table.append((subtable_offset, first_file_id, parent_id))
        self.section_size += 8

        if self.has_nametable:
            self.sub_tables[directory_id] = []
            
            # Concatenate type and length
            type_length = 0x80 | len(directory_name)

            # Append directory to parent directory
            self.sub_tables[parent_id].append((type_length, directory_name, directory_id))
            self.section_size += 3 + len(directory_name)


    def add_file(self, parent_id: int, file_name: str) -> None:
        """
        Adds a file to the BTNF

        Args:
            parent_id (int): Parent directory's id
            file_name (str): File name
        """
        if self.has_nametable:
            # Add to parent directory
            self.sub_tables[parent_id].append((len(file_name), file_name))
            self.section_size += len(file_name) + 1
        
    
    def load(self, reader: IOHandler) -> None:
        self.magic_id = reader.read(StructModes.uint32)
        self.section_size = reader.read(StructModes.uint32)

        # Read main table
        # Root directory
        root_fnt_offset = reader.read(StructModes.uint32)
        root_first_file = reader.read(StructModes.uint16)
        dir_number = reader.read(StructModes.uint16)
        self.main_table = [(root_fnt_offset, root_first_file, dir_number)]

        position = 16
        
        # Read all directories
        for _ in range(1, dir_number):
            fnt_offset = reader.read(StructModes.uint32)
            first_file = reader.read(StructModes.uint16)
            subdir_number = reader.read(StructModes.uint16)
            position += 8

            self.main_table.append((fnt_offset, first_file, subdir_number))

        # If position is at the header size, end... else it has a nametable
        # TODO Not useful for now but can be someday maybe
        file_id = 0
        while position != self.section_size:
            self.has_nametable = True
            type_length = reader.read(StructModes.uint8)
            # 0x80 is reserved and 0x00 sets the end of the table
            if type_length == 0x00:
                pass
            elif type_length < 0x80:
                # It's a file! 
                file_name = bytearray()
                for _ in range(0, type_length):
                    file_name.append(reader.read(StructModes.uint8))


            elif type_length > 0x80:
                pass    
        

    def save(self, writer: IOHandler) -> IOHandler:
        writer.write(StructModes.uint32, self.magic_id)
        writer.write(StructModes.uint32, self.section_size)

        # Write directories
        for (offset, first_file_position, parent_directory) in self.main_table:
            writer.write(StructModes.uint32, offset)
            writer.write(StructModes.uint16, first_file_position)
            writer.write(StructModes.uint16, parent_directory)
        
        # If has a nametable, write it
        if self.has_nametable:
            for sub_table in self.sub_tables.values():
                for item in sub_table:
                    type_length = item[0]
                    name = item[1]

                    writer.write(StructModes.uint8, type_length)
                    for char in name:
                        writer.write(StructModes.uint8, ord(char))

                    # Check if directory
                    if type_length > 0x80:
                        # We know from here that there is a third item
                        directory_id = item[2] # type: ignore
                        writer.write(StructModes.uint16, directory_id) # type: ignore

        return writer
        

class GMIF(Editable, Loadable, Savable):
    magic_id: int # uint32
    section_size: int # uint32
    files: bytes 


    def __init__(self) -> None:
        super().__init__()
        self.magic_id = int.from_bytes(b'GMIF', 'little')
        self.section_size = 8
        self.files = b''
        self.restrict('files', 'bytes_type', lambda value: isinstance(value, bytes))

    def define(self, builder: AtomicStructBuilder, *_: Any):
        builder.add_field('magic_id', FieldTypes.uint32_t)\
               .add_field('section_size', FieldTypes.uint32_t)\
               .add_custom('files', 'rawdata')

        
    def add_file(self, file: IOHandler, offset: int, fill: bytes = b'\xFF'):
        """
        Adds a file to GMIF (bytes values)

        Args:
            file (IOHandler): The file to add
        """
        content = file.getvalue()
        self.files += fill * offset + content
        self.section_size += offset + len(content)


    def load(self, reader: IOHandler) -> None:
        self.magic_id = reader.read(StructModes.uint32)
        self.section_size = reader.read(StructModes.uint32)
        self.files = reader.read_bytes(self.section_size - 8)


    def save(self, writer: IOHandler) -> IOHandler:
        writer.write(StructModes.uint32, self.magic_id)
        writer.write(StructModes.uint32, self.section_size)
        writer.write_bytes(self.files)
        return writer


class NARC(Editable, Loadable, Savable, Exportable):
    header: GenericHeader
    btaf: BTAF
    btnf: BTNF
    gmif: GMIF


    def __init__(self) -> None:
        """
        NARC archive file. For now no nametable because real scary...
        """
        super().__init__()
        self.header = GenericHeader(magic_id=ExtensionEnum.NARC.magic_bytes, header_size=0x10, subsection_number=3)
        self.btaf = BTAF()
        self.btnf = BTNF()
        self.gmif = GMIF()


    def define(self, builder: AtomicStructBuilder, *_: Any) -> None:
        builder.add_custom('header', 'generic_header')\
               .add_custom('btaf', 'BTAF')\
               .add_custom('btnf', 'BTNF')\
               .add_custom('gmif', 'GMIF')
        

    def add_file(self, file: IOHandler, offset: int = 0, file_name: str = '', parent_id: int = 0):
        content = file.getvalue()
        self.btaf.add_file(len(content), offset)
        self.btnf.add_file(parent_id, file_name)
        self.gmif.add_file(file, offset)
        self.header.section_size = 0x10 + self.btaf.section_size + self.btnf.section_size + self.gmif.section_size

    
    def load(self, reader: IOHandler) -> None:
        self.header.load(reader)
        self.btaf.load(reader)
        self.btnf.load(reader)
        self.gmif.load(reader)

    
    def save(self, writer: IOHandler) -> IOHandler:
        self.header.save(writer)
        self.btaf.save(writer)
        self.btnf.save(writer)
        self.gmif.save(writer)
        return writer
    
    
    def export(self, export_path, export_name: str) -> None:
        # Checks if directory name exists, if so delete everything
        export_directory = os.path.join(export_path, export_name)
        if os.path.isdir(export_directory):
            shutil.rmtree(export_directory)
        
        # Create directory
        os.mkdir(export_directory)

        # Get full file content
        files_content = self.gmif.files
        file_index = 0
        for start, end in self.btaf.files_offset:
            # Get file content and determine extension
            file_content = files_content[start:end]
            if len(file_content) >= 4:
                extension = ExtensionEnum.from_magic_bytes(file_content[0:4])
            else:
                extension = 'bin'

            # Open new file and write content
            file_handler = IOFileHandler(os.path.join(export_directory, f'{export_name:s}_{file_index:d}.{extension:s}'), 'w')
            file_handler.write_bytes(file_content)
            file_index += 1