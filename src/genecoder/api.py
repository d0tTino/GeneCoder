from __future__ import annotations
# ruff: noqa: ANN401

"""Public abstract interfaces for GeneCoder plugins."""

from abc import ABC, abstractmethod
from typing import Any, Mapping, Tuple


__all__ = ["Codec", "FEC", "Simulator", "Visualizer"]


class Codec(ABC):
    """Abstract base class for stateless codecs.

    Implementations must provide :meth:`encode` and :meth:`decode`
    methods.  Extra keyword arguments are accepted to allow codecs to
    expose optional behaviour without changing the interface.
    """

    @abstractmethod
    def encode(self, data: bytes, /, **kwargs: Any) -> Any:
        """Return an encoded representation of ``data``.

        Parameters
        ----------
        data:
            Raw byte payload to be encoded.
        **kwargs:
            Optional codec specific parameters.

        Returns
        -------
        Any
            Encoded representation of the input bytes.
        """

    @abstractmethod
    def decode(self, encoded: Any, /, **kwargs: Any) -> bytes:
        """Decode ``encoded`` back into the original byte sequence.

        Parameters
        ----------
        encoded:
            The encoded object returned by :meth:`encode`.
        **kwargs:
            Optional codec specific parameters.

        Returns
        -------
        bytes
            The original byte payload.
        """


class FEC(ABC):
    """Abstract base class for forward error correction backends."""

    @abstractmethod
    def encode(self, data: bytes, /, **kwargs: Any) -> Tuple[bytes, Mapping[str, Any]]:
        """Return FEC protected data and metadata.

        Parameters
        ----------
        data:
            Payload bytes to protect.
        **kwargs:
            Backend specific options.

        Returns
        -------
        tuple[bytes, Mapping[str, Any]]
            Tuple of encoded bytes and auxiliary information.
        """

    @abstractmethod
    def decode(self, encoded: bytes, info: Mapping[str, Any], /, **kwargs: Any) -> Tuple[bytes, int]:
        """Recover the original data from ``encoded`` using ``info``.

        Parameters
        ----------
        encoded:
            Bytes produced by :meth:`encode`.
        info:
            Auxiliary information returned by :meth:`encode`.
        **kwargs:
            Backend specific options.

        Returns
        -------
        tuple[bytes, int]
            The recovered payload and number of corrected errors.
        """


class Simulator(ABC):
    """Abstract base class for read simulators."""

    @abstractmethod
    def simulate(self, sequence: str) -> str:
        """Return a possibly corrupted version of ``sequence``.

        Parameters
        ----------
        sequence:
            Input DNA sequence.

        Returns
        -------
        str
            Simulated read sequence.
        """

    def with_profile(self, profile: str) -> "Simulator":
        """Return a copy of the simulator configured for ``profile``.

        Implementations may override this method to support applying
        external error profiles.  The default implementation raises
        :class:`NotImplementedError` to signal that the feature is not
        available.

        Parameters
        ----------
        profile:
            Identifier for the error profile.

        Returns
        -------
        Simulator
            A simulator instance configured with the requested profile.
        """

        raise NotImplementedError


class Visualizer(ABC):
    """Abstract base class for sequence visualizers."""

    @abstractmethod
    def visualize(self, sequence: str, /, **kwargs: Any) -> Any:
        """Produce a visualization of ``sequence``.

        Parameters
        ----------
        sequence:
            DNA sequence or other result object to visualise.
        **kwargs:
            Optional visualisation parameters.

        Returns
        -------
        Any
            The visualisation object produced by the implementation.
        """

