from typing import Any, Callable
from rawdb.event.event import Event


class Singleton(type):
    """
    Meta class used to implement a singleton.
    """

    # Used to store instances
    _instances: dict[Any, Any] = {}

    def __call__(self, *args, **kwargs):
        if self not in self._instances:
            instance = super().__call__(*args, **kwargs)
            self._instances[self] = instance
        return self._instances[self]


class EventManager(metaclass=Singleton):
    """
    Manager that will notify all registered listeners of an event 
    when it is fired. Is implemented as a singleton, any new creation
    will return the same instance.

    Args:
        a (int): z
    """

    _registered_handlers: dict[str, list[Callable[[Event], None]]]

    
    def __init__(self) -> None:
        self._registered_handlers = {}


    def register_event_handler(self, event_name: str, event_handler: Callable[[Event], None]):
        """
        Registers a handler for an event identified by its name

        Args:
            event_name (str): Name of the event
            event_handler (Callable[[Event], None]): Handler to execute when the event is fired
        """
        if event_name in self._registered_handlers:
            self._registered_handlers[event_name].append(event_handler)
        else:
            self._registered_handlers[event_name] = [event_handler]

    
    def remove_event_handler(self, event_name: str, event_handler: Callable[[Event], None]):
        """
        Removes the handler for an event identified by its name

        Args:
            event_name (str): Name of the event
            event_handler (Callable[[Event], None]): Handler to remove
        """
        if event_name in self._registered_handlers:
            self._registered_handlers[event_name].remove(event_handler)

    
    def remove_all_handlers(self, event_name: str):
        """
        Removes all handlers for an event identified by its name

        Args:
            event_name (str): Name of the event
        """
        if event_name in self._registered_handlers:
            del self._registered_handlers[event_name]


    def fire(self, event: Event) -> None:
        """
        Fire the event and notify all registered handlers

        Args:
            event (Event): _description_
        """
        if event.name not in self._registered_handlers:
            print(f'WARNING: Event {event.name:s} is not registered')
        else: 
            for event_handler in self._registered_handlers[event.name]:
                event_handler(event)
                
                # Check if event has been cancelled
                if event.cancelled:
                    break
