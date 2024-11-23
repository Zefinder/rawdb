from abc import ABCMeta, abstractmethod


class Exportable(metaclass=ABCMeta):
    """
    Interface that make objects implement the `export` method
    """

    @abstractmethod
    def export(self, export_path: str, export_name: str) -> None:
        """
        Exports this object to another format. Useful to export a file format object to
        a file or to a directory (with files in it).

        Args:
            export_path (str): File's path
            export_name (str): File or directory's name
        """
        pass