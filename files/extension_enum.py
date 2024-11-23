from enum import Enum


class ExtensionEnum(Enum):
    magic_bytes: bytes
    extension: str

    NCLR = b'RLCN', 'nclr'
    NCGR = b'RGCN', 'ncgr'
    NSCR = b'RCSN', 'nscr'
    NANR = b'RNAN', 'nanr'
    NCER = b'RECN', 'ncer'
    NARC = b'NARC', 'narc'
    SDAT = b'SDAT', 'sdat'
    
    # Verify! 
    SSEQ = b'SSEQ', 'sseq'
    SSAR = b'SSAR', 'ssar'
    SWAR = b'SWAR', 'swar'
    SBNK = b'SBNK', 'sbnk'
    
    
    def __init__(self, magic_bytes: bytes, extension: str) -> None:
        self.magic_bytes = magic_bytes
        self.extension = extension
    

    @classmethod
    def from_magic_bytes(cls, magic_bytes: bytes) -> 'ExtensionEnum | None':
        for c in cls:
            if c.value[0] == magic_bytes:
                return c.value[1]
        return None
