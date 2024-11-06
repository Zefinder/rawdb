from abc import ABCMeta, abstractmethod
import os
import time
from typing import Any
from zipfile import ZipFile, ZipInfo

from rawdb.util import natsort_key
from rawdb.util.io import BinaryIO

class Archive(object, metaclass=ABCMeta):
    files: list[Any]
    extension: str
    _external_attr: int


    def __init__(self) -> None:
        self.files = []
        self.extension = '.bin'
        self._external_attr = 33152 << 16 # WHY??????


    @classmethod
    def from_zip(cls, archive_name: str, mode: str ='r') -> 'Archive':
        """
        Creates a new Archive object from a zip archive

        Args:
            archive_name (str): Archive's name
            mode (str, optional): Archive's mode, must be either 'r', 'w', 'x' or 'a'. Defaults to 'w'.
        """ 
        if mode not in ('r', 'w', 'x', 'a'):
            # TODO Raise an error? 
            return cls()

        archive_obj = cls()
        with ZipFile(archive_name, mode) as archive:
            for name in sorted(archive.namelist(), key=natsort_key):
                archive_obj.add(archive.read(name))

        return archive_obj

    def get(self, index: int) -> Any:
        """
        Gets the stored item at a specific index

        Args:
            index (int): Item's index

        Returns:
            Any: Stored item
        """
        return self.files[index]
    

    def add(self, data: Any) -> None:
        """
        Adds an item to the list

        Args:
            data (Any): Item to add
        """
        self.files.append(data)


    def replace(self, index: int, data: Any) -> None:
        """
        Replaces an item at the specified index

        Args:
            index (int): Specified index
            data (Any): New data
        """
        self.files[index] = data


    def reset(self) -> None:
        """
        Resets the archive
        """
        self.__init__()


    def delete(self, index: int = -1) -> Any:
        """
        Removes an item from the list at the specified index. 
        If the index is -1, the last item is removed.

        Args:
            index (int, optional): Index to remove. Defaults to -1.

        Returns:
            Any: Removed item
        """
        return self.files.pop(index)
        

    def export(self, archive_name: str, mode: str = 'w') -> None:
        """
        Exports this object to a zip archive containing added files.

        Args:
            archive_name (str): Archive's name
            mode (str, optional): Archive's mode, must be either 'r', 'w', 'x' or 'a'. Defaults to 'w'.
        """
        if mode not in ('r', 'w', 'x', 'a'):
            # TODO Raise an error? 
            return

        with ZipFile(archive_name, mode) as archive:
            # For each element create a new file 
            for index in range(0, len(self.files)):
                filename = f'{index:d}{self.extension:s}'
                date_time = time.localtime(time.time())[:6]

                zipinfo = ZipInfo(filename=filename, date_time=date_time)
                zipinfo.compress_type = archive.compression
                zipinfo.external_attr = self._external_attr

                # Write file
                archive.writestr(zipinfo, self.files[index])


    def export_dir(self, dir_name: str) -> None:
        """
        Exports this object to a directory containing added files.

        Args:
            dir_name (str): Directory's name
        """
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        
        for index in range(0, len(self.files)):
            filename = f'{index:d}{self.extension:s}'
            with open(os.path.join(dir_name, filename), 'w') as handle:
                handle.write(self.files[index])


    def __iter__(self):
        return iter(self.files)
    

    def __len__(self):
        return len(self.files)
    