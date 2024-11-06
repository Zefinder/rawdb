from abc import ABCMeta, abstractmethod

from rawdb.util.io import BinaryIO


class Loadable(metaclass=ABCMeta):
    """
    Interface that make objects implement the `load` method
    """

    @abstractmethod
    def load(self, reader: BinaryIO) -> None:
        """
        Loads what is in the reader in the object

        Args:
            reader (BinaryIO): Reader to read from 
        """
        pass