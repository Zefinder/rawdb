from abc import ABCMeta, abstractmethod

from rawdb.interfaces.binary_io import IOHandler


class Savable(metaclass=ABCMeta):
    """
    Interface that make objects implement the `save` method
    """

    @abstractmethod
    def save(self, writer: IOHandler) -> IOHandler:
        """
        Saves the object in the writer and returns it.

        Args:
            writer (IOHandler): Writer to write to 

        Returns:
            IOHandler: The same input writer but with the object in it
        """
        pass