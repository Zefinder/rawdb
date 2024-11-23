from typing import Any
from rawdb.atomic.atomic_struct import AtomicStructBuilder, FieldTypes
from rawdb.generic.editable import Editable
from rawdb.interfaces.binary_io import IOHandler, StructModes
from rawdb.interfaces.loadable import Loadable
from rawdb.interfaces.savable import Savable


class NTFP(Editable, Loadable, Savable):
    palette_color: int # uint16


    def __init__(self) -> None:
        super().__init__()

    
    def define(self, builder: AtomicStructBuilder, *_: Any) -> None:
        builder.add_field('palette_color', FieldTypes.uint16_t)


    def load(self, reader: IOHandler) -> None:
        self.palette_color = reader.read(StructModes.uint16)


    def save(self, writer: IOHandler) -> IOHandler:
        writer.write(StructModes.uint16, self.palette_color)
        return writer
    

class NTFT(Editable, Loadable, Savable):
    tile_data: int # uint8 (4 or 8 bits)

    def __init__(self) -> None:
        super().__init__()


    def define(self, builder: AtomicStructBuilder, *_: Any):
        builder.add_field('tile_data', FieldTypes.uint8_t)

    
    def load(self, reader: IOHandler) -> None:
        self.tile_data = reader.read(StructModes.uint8)

    
    def save(self, writer: IOHandler) -> IOHandler:
        writer.write(StructModes.uint8, self.tile_data)
        return writer
    

class NTFS(Editable, Loadable, Savable):
    screen_data: int # uint16
    
    def __init__(self) -> None:
        super().__init__()

    
    def define(self, builder: AtomicStructBuilder, *_: Any):
        builder.add_field('screen_data', FieldTypes.uint16_t)


    def load(self, reader: IOHandler) -> None:
        self.screen_data = reader.read(StructModes.uint16)

    
    def save(self, writer: IOHandler) -> IOHandler:
        writer.write(StructModes.uint16, self.screen_data)
        return writer
