class Converter:
    """The base class of custom converters that require the :class:`.Context`
    to be passed to be useful.

    This allows you to implement converters that function similar to the
    special cased ``discord`` classes.

    Classes that derive from this should override the :meth:`~.Converter.convert`
    method to do its conversion logic. This method must be a :ref:`coroutine <coroutine>`.
    """

    def convert(self, ctx, argument):
        """The method to override to do conversion logic.

        If an error is found while converting, it is recommended to
        raise a :exc:`.CommandError` derived exception as it will
        properly propagate to the error handlers.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context that the argument is being used in.
        argument: :class:`str`
            The argument that is being converted.
        """
        raise NotImplementedError("Derived classes need to implement this.")


class _Greedy:
    __slots__ = ("converter",)

    def __init__(self, *, converter=None):
        self.converter = converter

    def __getitem__(self, params):
        if not isinstance(params, tuple):
            params = (params,)
        if len(params) != 1:
            raise TypeError("Greedy[...] only takes a single argument")
        converter = params[0]

        if not (
            callable(converter)
            or isinstance(converter, Converter)
            or hasattr(converter, "__origin__")
        ):
            raise TypeError("Greedy[...] expects a type or a Converter instance.")

        if converter is str or converter is type(None) or converter is _Greedy:
            raise TypeError("Greedy[%s] is invalid." % converter.__name__)

        return self.__class__(converter=converter)


Greedy = _Greedy()
