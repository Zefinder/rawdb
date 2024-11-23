from typing import Any
from rawdb.atomic.atomic_struct import AtomicStructBuilder, FieldTypes
from rawdb.files.extension_enum import ExtensionEnum
from rawdb.files.generic_header import GenericHeader
from rawdb.files.graphics.tile_format import NTFP
from rawdb.generic.editable import Editable
from rawdb.interfaces.binary_io import IOHandler, StructModes
from rawdb.interfaces.exportable import Exportable
from rawdb.interfaces.loadable import Loadable
from rawdb.interfaces.savable import Savable


class TTLP(Editable, Loadable, Savable):
    magic_id: int # uint32
    section_size: int # uint32
    palette_bit_depth: int # uint32
    padding: int # uint32
    palette_data_size: int # uint32
    colors_per_palette: int # uint32
    palette_data: list[NTFP] # list of palettes


    def __init__(self) -> None:
        super().__init__()
        self.palette_data = []

        # Add restriction on the size of the number of palettes
        self.restrict('palette_data', 'max_palette_number', lambda value: len(value) <= 256)


    def define(self, builder: AtomicStructBuilder, *_: Any):
        # Add default values, they rarely change...
        builder.add_field('magic_id', FieldTypes.uint32_t)
        builder.add_field('section_size', FieldTypes.uint32_t, default=0x218)
        builder.add_field('palette_bit_depth', FieldTypes.uint32_t)
        builder.add_field('padding', FieldTypes.uint32_t, default=0)
        builder.add_field('palette_data_size', FieldTypes.uint32_t, default=0x200)
        builder.add_field('colors_per_palette', FieldTypes.uint32_t, default=0x10)
        builder.add_pointer_custom('palette_data', 'NTFP')


    def add_color(self, color: int):
        """
        Adds a color, must be in BGR555 format

        Args:
            color (int): Color to add
        """
        palette = NTFP()
        palette.palette_color = color
        self.palette_data.append(palette)


    def load(self, reader: IOHandler) -> None:
        self.magic_id = reader.read(StructModes.uint32)
        self.section_size = reader.read(StructModes.uint32)
        self.palette_bit_depth = reader.read(StructModes.uint32)
        self.padding = reader.read(StructModes.uint32)
        self.palette_data_size = reader.read(StructModes.uint32)
        self.colors_per_palette = reader.read(StructModes.uint32)

        colors_to_read = (self.section_size - 0x18) >> 1
        self.palette_data = []
        for _ in range(0, colors_to_read):
            palette_color = NTFP()
            palette_color.load(reader)
            self.palette_data.append(palette_color)

    
    def save(self, writer: IOHandler) -> IOHandler:
        writer.write(StructModes.uint32, self.magic_id)
        writer.write(StructModes.uint32, self.section_size)
        writer.write(StructModes.uint32, self.palette_bit_depth)
        writer.write(StructModes.uint32, self.padding)
        writer.write(StructModes.uint32, self.palette_data_size)
        writer.write(StructModes.uint32, self.colors_per_palette)

        for ntfp in self.palette_data:
            ntfp.save(writer)

        return writer


class NCLR(Editable, Loadable, Savable):
    header: GenericHeader
    ttlp: TTLP


    def __init__(self) -> None:
        super().__init__()
        self.header = GenericHeader(magic_id=ExtensionEnum.NCLR.magic_bytes, header_size=0x10, subsection_number=2)
        self.ttlp = TTLP()


    def define(self, builder: AtomicStructBuilder, *_: Any):
        builder.add_custom('header', 'GenericHeader')
        builder.add_custom('ttlp', 'TTLP')


    def get_palettes(self) -> list[list[int]]:
        """
        Returns palettes with their colors. If there is only one palette of 256 colors,
        will be a list of 1 palette. Else will be up to 16 lists of 16 colors. 

        Returns:
            list[int]: palettes with their colors
        """
        palettes = []
        if self.ttlp.palette_bit_depth == 4: # 8 bits depth
            palette = []
            for palette_color in self.ttlp.palette_data:
                palette.append(palette_color.palette_color)
            palettes.append(palette)
                    
        else: # 4 bits depth
            index = 0
            palette = []
            for palette_color in self.ttlp.palette_data:
                palette.append(palette_color.palette_color)
                
                index += 1
                
                # When 16 colors placed, reset the index and the palette
                if index == 16:
                    index = 0
                    palettes.append(palette)
                    palette = []

        return palettes

    
    def load(self, reader: IOHandler) -> None:
        self.header.load(reader)
        self.ttlp.load(reader)


    def save(self, writer: IOHandler) -> IOHandler:
        self.header.save(writer)
        self.ttlp.save(writer)

        return writer
