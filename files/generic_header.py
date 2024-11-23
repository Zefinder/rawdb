from typing import Any
from rawdb.atomic.atomic_struct import AtomicStructBuilder, FieldTypes
from rawdb.generic.editable import Editable
from rawdb.interfaces.binary_io import IOHandler, StructModes
from rawdb.interfaces.loadable import Loadable
from rawdb.interfaces.savable import Savable
from rawdb.util.io import IOBytesHandler


class GenericHeader(Editable, Loadable, Savable):
    magic_id: int # uint32
    unused: int # uint32
    section_size: int # uint32
    header_size: int # uint16
    subsection_number: int # uint16


    def __init__(self, magic_id: bytes = b'', section_size: int = 0, header_size: int = 0, subsection_number: int = 0) -> None:
        """
        Represents the generic header. The header has a size of 16 bytes:
        - Magic ID, or magic bytes (4 bytes)
        - Constant, apparently a constant equal to 0xFFFE0001, 
        but sometimes 0xFEFF0001 (4 bytes)
        - Section size, size of the section (if of a file, then the file
        size) (4 bytes)
        - Header size, size of the header (2 bytes)
        - Number of sub-sections (2 bytes)

        Args:
            magic_id (bytes, optional): Magic bytes of the format. Defaults to b''.
            section_size (int, optional): Section size. Defaults to 0.
            header_size (int, optional): Header size. Defaults to 0.
            subsection_number (int, optional): Number of subsections. Defaults to 0.
        """
        super().__init__()

        if magic_id != b'':
            self.magic_id = int.from_bytes(magic_id, 'little')
        
        self.section_size = section_size
        self.header_size = header_size
        self.subsection_number = subsection_number


    def define(self, builder: AtomicStructBuilder, *_: Any):
        builder.add_field('magic_id', FieldTypes.uint32_t)\
               .add_field('unused', FieldTypes.uint32_t, default=0x0100FEFF)\
               .add_field('section_size', FieldTypes.uint32_t)\
               .add_field('header_size', FieldTypes.uint16_t)\
               .add_field('subsection_number', FieldTypes.uint16_t)
        
    
    def load(self, reader: IOHandler) -> None:
        self.magic_id = reader.read(StructModes.int32)
        self.unused = reader.read(StructModes.uint32)
        self.section_size = reader.read(StructModes.uint32)
        self.header_size = reader.read(StructModes.uint16)
        self.subsection_number = reader.read(StructModes.uint16)
    

    def save(self, writer: IOHandler) -> IOHandler:
        writer.write(StructModes.uint32, self.magic_id)
        writer.write(StructModes.uint32, self.unused)
        writer.write(StructModes.uint32, self.section_size)
        writer.write(StructModes.uint16, self.header_size)
        writer.write(StructModes.uint16, self.subsection_number)
        return writer
