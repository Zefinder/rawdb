from typing import Any, Callable


class RestrictionError(Exception):
    """
    Raised when a value does not meet the imposed restriction
    """
    
    def __init__(self, restriction_name: str, value: Any, name: str) -> None:
        super().__init__(f'{restriction_name:s}: Value <{value}> does not respect restriction "{name:s}"')


class Restriction(object):
    """
    Restriction definition on an attribute's value and/or type

    Methods
    -------
    restrict
        Add restriction
    validate
        Check that a value is valid
    """

    restriction_name: str
    validators: list[tuple[str, Callable[[Any], bool]]]


    def __init__(self, restriction_name: str, *validators: tuple[str, Callable[[Any], bool]]) -> None:
        self.restriction_name = restriction_name
        self.validators = []

        for validator in validators:
            self.validators.append(validator)


    def restrict(self, name: str, validator: Callable[[Any], bool]) -> None:
        """Add a restriction to the values

        Args:
            name (str): Restriction name
            validator ((Editable, Any) -> bool): Validator method

        Examples:
        >>> restriction = Restriction('test')
        >>> def value_is_even(editable, value):
                return value % 2
        >>> restriction.restrict('value_is_even', value_is_even)
        >>> restriction.validate(2)
        >>> restriction.validate(3)
        Traceback (most recent call last):
            ...
        RestrictionError: test: Value <3> does not respect restriction "value_is_even"
        >>> restriction.restrict('minimum 7', lambda value: value >= 7)
        >>> restriction.validate(8)
        >>> restriction.validate(4)
        Traceback (most recent call last):
            ...
        RestrictionError: test: Value <4> does not respect restriction "minimum 7"
        >>> restriction.validate(9)
        Traceback (most recent call last):
            ...
        RestrictionError: test: Value <9> does not respect restriction "value_is_even"
        >>>
        """

        self.validators.append((name, validator))


    def validate(self, value: Any) -> None:
        """
        Validates a value executing all registered validators

        Args:
            value (Any): Value to validate

        Raises:
            RestrictionError: If a restriction is not met
        """
        for (name, validator) in self.validators:
            if not validator(value):
                raise RestrictionError(self.restriction_name, value, name)