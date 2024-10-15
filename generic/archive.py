
import abc
import os
import time
import zipfile

from rawdb.util import natsort_key
from rawdb.util.io import BinaryIO

# TODO Verify that everything is correct here
# TODO Add type hints
class Archive(object):
    # __metaclass__ = abc.ABCMeta
    files = {}
    extension = '.bin'

    def get(self, ref):
        return self.files[ref]

    def add(self, ref, data):
        self.files[ref] = data

    def reset(self):
        """Resets archive"""
        self.__init__()

    def delete(self, ref):
        self.files.pop(ref)

    def flush(self):
        pass

    def __iter__(self):
        return iter(self.files)

    def __len__(self):
        return len(self.files)

    @abc.abstractmethod
    def save(self, writer=None):
        pass

    def get_value(self):
        """String of this Archive"""
        writer = BinaryIO()
        return self.save(writer).getvalue()

    def export(self, handle, mode='w'):
        """Build a zip archive from files

        Parameters
        ----------
        handle : File-like or string
            Destination file handle to write to
        """
        with zipfile.ZipFile(handle, mode) as archive:
            try:
                names = self.files.keys()
            except AttributeError:
                names = range(len(self.files))
            for name in names:
                zipinfo = zipfile.ZipInfo(
                    str(name)+self.extension,
                    date_time=time.localtime(time.time())[:6])
                zipinfo.compress_type = archive.compression
                zipinfo.external_attr = 33152 << 16
                archive.writestr(zipinfo, self.files[name])
        return handle

    def export_dir(self, dir_name):
        """Build a directory from files

        Parameters
        ----------
        dir_name : string
            Destination directory. It will be created if it does not exist.
        """
        try:
            os.makedirs(dir_name)
        except:
            pass
        try:
            names = self.files.keys()
        except AttributeError:
            names = range(len(self.files))
        for name in names:
            with open(os.path.join(dir_name, str(name)+self.extension), 'w')\
                    as handle:
                handle.write(self.files[name])
        return dir_name

    def import_(self, handle, mode='r'):
        """Import files from the zip archive into this

        Parameters
        ----------
        handle : File-like or string
            Target file handle to read from
        mode : string
            Mode to read from handle
        """
        self.reset()
        with zipfile.ZipFile(handle, mode) as archive:
            for name in sorted(archive.namelist(), key=natsort_key):
                if name.endswith(self.extension):
                    internalname = name[:-len(self.extension)]
                else:
                    internalname = name
                self.add(internalname, archive.read(name))
        self.flush()


class ArchiveList(Archive):
    files = []

    def get(self, ref):
        return self.files[ref]

    def add(self, ref=None, data=''):
        self.files.append(data)
