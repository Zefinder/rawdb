from abc import ABCMeta, abstractmethod

from rawdb.util.io import BinaryIO


class Savable(metaclass=ABCMeta):
    """
    Interface that make objects implement the `save` method
    """

    @abstractmethod
    def save(self, writer: BinaryIO) -> BinaryIO:
        """
        Saves the object in the writer and returns it.

        Args:
            writer (BinaryIO): Writer to write to 

        Returns:
            BinaryIO: The same input writer but with the object in it
        """
        pass