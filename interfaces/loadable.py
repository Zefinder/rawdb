from abc import ABCMeta, abstractmethod

from rawdb.interfaces.binary_io import IOHandler


class Loadable(metaclass=ABCMeta):
    """
    Interface that make objects implement the `load` method
    """

    @abstractmethod
    def load(self, reader: IOHandler) -> None:
        """
        Loads what is in the reader in the object

        Args:
            reader (IOHandler): Reader to read from 
        """
        pass