from typing import Any


class Event(object):
    """
    Object that represents an event with its data. It is passed 
    to every listner that registers it. Registering is made
    with the event's name

    Args:
        name (str): Name of event
        source (object): Source of event
        data (Any): Event's data

    Attributes:
        name (str): Name of event
        source (object): Source of event
        data (Any): Event's data
        cancelled (bool): Whether this event should continue to propagate. 
        Use Event.cancel() to cancel an event
        success (bool): Whether this event has successfully executed
    """
    name: str
    source: object
    data: Any
    cancelled: bool


    def __init__(self, name: str, source: object, data: Any = None) -> None:
        self.name = name
        self.source = source
        self.data = data
        self.cancelled = False

    
    def cancel(self) -> None:
        """Cancel the event and stops its propagation"""
        self.cancelled = True

    
    @property
    def success(self) -> bool:
        """Whether or not this event has successfully executed"""
        return not self.cancelled