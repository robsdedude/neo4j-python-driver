# Copyright (c) "Neo4j"
# Neo4j Sweden AB [https://neo4j.com]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import annotations

import typing as t
from enum import Enum
from urllib.parse import parse_qs

from .exceptions import ConfigurationError as _ConfigurationError


if t.TYPE_CHECKING:
    import typing_extensions as te


__all__ = [
    "DRIVER_BOLT",
    "DRIVER_NEO4J",
    "SECURITY_TYPE_NOT_SECURE",
    "SECURITY_TYPE_SECURE",
    "SECURITY_TYPE_SELF_SIGNED_CERTIFICATE",
    "URI_SCHEME_BOLT",
    "URI_SCHEME_BOLT_ROUTING",
    "URI_SCHEME_BOLT_SECURE",
    "URI_SCHEME_BOLT_SELF_SIGNED_CERTIFICATE",
    "URI_SCHEME_NEO4J",
    "URI_SCHEME_NEO4J_SECURE",
    "URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE",
    "NotificationCategory",
    "NotificationClassification",
    "NotificationDisabledCategory",
    "NotificationDisabledClassification",
    "NotificationMinimumSeverity",
    "NotificationSeverity",
    "RoutingControl",
    "TelemetryAPI",
    "parse_routing_context",
    "parse_uri_scheme",
]


class NotificationMinimumSeverity(str, Enum):
    """
    Filter notifications returned by the server by minimum severity.

    For GQL-aware servers, notifications are a subset of GqlStatusObjects.
    See also :attr:`.GqlStatusObject.is_notification`.

    Inherits from :class:`str` and :class:`enum.Enum`.
    Every driver API accepting a :class:`.NotificationMinimumSeverity` value
    will also accept a string::

        >>> NotificationMinimumSeverity.OFF == "OFF"
        True
        >>> NotificationMinimumSeverity.WARNING == "WARNING"
        True
        >>> NotificationMinimumSeverity.INFORMATION == "INFORMATION"
        True

    .. seealso::
        driver config :ref:`driver-notifications-min-severity-ref`,
        session config :ref:`session-notifications-min-severity-ref`

    .. versionadded:: 5.7
    """

    OFF = "OFF"
    WARNING = "WARNING"
    INFORMATION = "INFORMATION"


if t.TYPE_CHECKING:
    T_NotificationMinimumSeverity = t.Union[
        NotificationMinimumSeverity,
        te.Literal[
            "OFF",
            "WARNING",
            "INFORMATION",
        ],
    ]
    __all__.append("T_NotificationMinimumSeverity")


class NotificationSeverity(str, Enum):
    """
    Server-side notification severity.

    Inherits from :class:`str` and :class:`enum.Enum`.
    Hence, can also be compared to its string value::

        >>> NotificationSeverity.WARNING == "WARNING"
        True
        >>> NotificationSeverity.INFORMATION == "INFORMATION"
        True
        >>> NotificationSeverity.UNKNOWN == "UNKNOWN"
        True

    Example::

        import logging

        from neo4j import NotificationSeverity


        log = logging.getLogger(__name__)

        ...

        summary = session.run("RETURN 1").consume()

        for notification in summary.summary_notifications:
            severity = notification.severity_level
            if severity == NotificationSeverity.WARNING:
                # or severity == "WARNING"
                log.warning("%r", notification)
            elif severity == NotificationSeverity.INFORMATION:
                # or severity == "INFORMATION"
                log.info("%r", notification)
            else:
                # assert severity == NotificationSeverity.UNKNOWN
                # or severity == "UNKNOWN"
                log.debug("%r", notification)

    .. seealso:: :attr:`.SummaryNotification.severity_level`

    .. versionadded:: 5.7
    """

    WARNING = "WARNING"
    INFORMATION = "INFORMATION"
    #: Used when the server provides a Severity which the driver is unaware of.
    #: This can happen when connecting to a server newer than the driver.
    UNKNOWN = "UNKNOWN"


class NotificationDisabledCategory(str, Enum):
    """
    Filter notifications returned by the server by category.

    For GQL-aware servers, notifications are a subset of GqlStatusObjects.
    See also :attr:`.GqlStatusObject.is_notification`.

    Inherits from :class:`str` and :class:`enum.Enum`.
    Every driver API accepting a :class:`.NotificationDisabledCategory` value
    will also accept a string::

        >>> NotificationDisabledCategory.UNRECOGNIZED == "UNRECOGNIZED"
        True
        >>> NotificationDisabledCategory.PERFORMANCE == "PERFORMANCE"
        True
        >>> NotificationDisabledCategory.DEPRECATION == "DEPRECATION"
        True

    .. seealso::
        driver config :ref:`driver-notifications-disabled-categories-ref`,
        session config :ref:`session-notifications-disabled-categories-ref`

    .. versionadded:: 5.7

    .. versionchanged:: 5.14
        Added categories :attr:`.SECURITY` and :attr:`.TOPOLOGY`.

    .. versionchanged:: 5.24
        Added category :attr:`.SCHEMA`.
    """

    HINT = "HINT"
    UNRECOGNIZED = "UNRECOGNIZED"
    UNSUPPORTED = "UNSUPPORTED"
    PERFORMANCE = "PERFORMANCE"
    DEPRECATION = "DEPRECATION"
    GENERIC = "GENERIC"
    SECURITY = "SECURITY"
    #: Requires server version 5.13 or newer.
    TOPOLOGY = "TOPOLOGY"
    #: Requires server version 5.17 or newer.
    SCHEMA = "SCHEMA"


class NotificationDisabledClassification(str, Enum):
    """
    Identical to :class:`.NotificationDisabledCategory`.

    This alternative is provided for a consistent naming with
    :attr:`.GqlStatusObject.classification`.

    **This is a preview**.
    It might be changed without following the deprecation policy.

    See also
    https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. seealso::
        driver config
        :ref:`driver-notifications-disabled-classifications-ref`,
        session config
        :ref:`session-notifications-disabled-classifications-ref`

    .. versionadded:: 5.22

    .. versionchanged:: 5.24
        Added classification :attr:`.SCHEMA`.
    """

    HINT = "HINT"
    UNRECOGNIZED = "UNRECOGNIZED"
    UNSUPPORTED = "UNSUPPORTED"
    PERFORMANCE = "PERFORMANCE"
    DEPRECATION = "DEPRECATION"
    GENERIC = "GENERIC"
    SECURITY = "SECURITY"
    #: Requires server version 5.13 or newer.
    TOPOLOGY = "TOPOLOGY"
    #: Requires server version 5.17 or newer.
    SCHEMA = "SCHEMA"


if t.TYPE_CHECKING:
    T_NotificationDisabledCategory = t.Union[
        NotificationDisabledCategory,
        NotificationDisabledClassification,
        te.Literal[
            "HINT",
            "UNRECOGNIZED",
            "UNSUPPORTED",
            "PERFORMANCE",
            "DEPRECATION",
            "GENERIC",
            "SECURITY",
            "TOPOLOGY",
            "SCHEMA",
        ],
    ]
    __all__.append("T_NotificationDisabledCategory")


class NotificationCategory(str, Enum):
    """
    Server-side notification category.

    Inherits from :class:`str` and :class:`enum.Enum`.
    Hence, can also be compared to its string value::

        >>> NotificationCategory.DEPRECATION == "DEPRECATION"
        True
        >>> NotificationCategory.GENERIC == "GENERIC"
        True
        >>> NotificationCategory.UNKNOWN == "UNKNOWN"
        True

    .. seealso:: :attr:`.SummaryNotification.category`

    .. versionadded:: 5.7

    .. versionchanged:: 5.14
        Added categories :attr:`.SECURITY` and :attr:`.TOPOLOGY`.

    .. versionchanged:: 5.24
        Added category :attr:`.SCHEMA`.
    """

    HINT = "HINT"
    UNRECOGNIZED = "UNRECOGNIZED"
    UNSUPPORTED = "UNSUPPORTED"
    PERFORMANCE = "PERFORMANCE"
    DEPRECATION = "DEPRECATION"
    GENERIC = "GENERIC"
    SECURITY = "SECURITY"
    TOPOLOGY = "TOPOLOGY"
    SCHEMA = "SCHEMA"
    #: Used when the server provides a Category which the driver is unaware of.
    #: This can happen when connecting to a server newer than the driver or
    #: before notification categories were introduced.
    UNKNOWN = "UNKNOWN"


class NotificationClassification(str, Enum):
    """
    Identical to :class:`.NotificationCategory`.

    This alternative is provided for a consistent naming with
    :attr:`.GqlStatusObject.classification`.

    **This is a preview**.
    It might be changed without following the deprecation policy.

    See also
    https://github.com/neo4j/neo4j-python-driver/wiki/preview-features

    .. seealso:: :attr:`.GqlStatusObject.classification`

    .. versionadded:: 5.22

    .. versionchanged:: 5.24
        Added classification :attr:`.SCHEMA`.
    """

    HINT = "HINT"
    UNRECOGNIZED = "UNRECOGNIZED"
    UNSUPPORTED = "UNSUPPORTED"
    PERFORMANCE = "PERFORMANCE"
    DEPRECATION = "DEPRECATION"
    GENERIC = "GENERIC"
    SECURITY = "SECURITY"
    TOPOLOGY = "TOPOLOGY"
    SCHEMA = "SCHEMA"
    #: Used when the server provides a Category which the driver is unaware of.
    #: This can happen when connecting to a server newer than the driver or
    #: before notification categories were introduced.
    UNKNOWN = "UNKNOWN"


class RoutingControl(str, Enum):
    """
    Selection which cluster members to route a query connect to.

    Inherits from :class:`str` and :class:`enum.Enum`.
    Every driver API accepting a :class:`.RoutingControl` value will also
    accept a string::

        >>> RoutingControl.READ == "r"
        True
        >>> RoutingControl.WRITE == "w"
        True

    .. seealso::
        :meth:`.AsyncDriver.execute_query`, :meth:`.Driver.execute_query`

    .. versionadded:: 5.5

    .. versionchanged:: 5.8

        * Renamed ``READERS`` to ``READ`` and ``WRITERS`` to ``WRITE``.
        * Stabilized from experimental.
    """

    READ = "r"
    WRITE = "w"


class TelemetryAPI(int, Enum):
    TX_FUNC = 0
    TX = 1
    AUTO_COMMIT = 2
    DRIVER = 3


if t.TYPE_CHECKING:
    T_RoutingControl = t.Union[
        RoutingControl,
        te.Literal["r", "w"],
    ]
    __all__.append("T_RoutingControl")


# TODO: 6.0 - make these 2 constants private and use an enum
DRIVER_BOLT: te.Final[str] = "DRIVER_BOLT"
DRIVER_NEO4J: te.Final[str] = "DRIVER_NEO4J"

# TODO: 6.0 - make these 3 constants private and use an enum
SECURITY_TYPE_NOT_SECURE: te.Final[str] = "SECURITY_TYPE_NOT_SECURE"
SECURITY_TYPE_SELF_SIGNED_CERTIFICATE: te.Final[str] = (
    "SECURITY_TYPE_SELF_SIGNED_CERTIFICATE"
)
SECURITY_TYPE_SECURE: te.Final[str] = "SECURITY_TYPE_SECURE"

URI_SCHEME_BOLT: te.Final[str] = "bolt"
URI_SCHEME_BOLT_SELF_SIGNED_CERTIFICATE: te.Final[str] = "bolt+ssc"
URI_SCHEME_BOLT_SECURE: te.Final[str] = "bolt+s"

URI_SCHEME_NEO4J: te.Final[str] = "neo4j"
URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE: te.Final[str] = "neo4j+ssc"
URI_SCHEME_NEO4J_SECURE: te.Final[str] = "neo4j+s"

URI_SCHEME_BOLT_ROUTING: te.Final[str] = "bolt+routing"


def parse_uri_scheme(scheme: str) -> tuple[str, str]:
    if scheme == URI_SCHEME_BOLT_ROUTING:
        raise _ConfigurationError(
            f"Uri scheme {scheme!r} has been renamed. "
            f"Use {URI_SCHEME_NEO4J!r}"
        )
    elif scheme == URI_SCHEME_BOLT:
        driver_type = DRIVER_BOLT
        security_type = SECURITY_TYPE_NOT_SECURE
    elif scheme == URI_SCHEME_BOLT_SELF_SIGNED_CERTIFICATE:
        driver_type = DRIVER_BOLT
        security_type = SECURITY_TYPE_SELF_SIGNED_CERTIFICATE
    elif scheme == URI_SCHEME_BOLT_SECURE:
        driver_type = DRIVER_BOLT
        security_type = SECURITY_TYPE_SECURE
    elif scheme == URI_SCHEME_NEO4J:
        driver_type = DRIVER_NEO4J
        security_type = SECURITY_TYPE_NOT_SECURE
    elif scheme == URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE:
        driver_type = DRIVER_NEO4J
        security_type = SECURITY_TYPE_SELF_SIGNED_CERTIFICATE
    elif scheme == URI_SCHEME_NEO4J_SECURE:
        driver_type = DRIVER_NEO4J
        security_type = SECURITY_TYPE_SECURE
    else:
        supported_schemes = [
            URI_SCHEME_BOLT,
            URI_SCHEME_BOLT_SELF_SIGNED_CERTIFICATE,
            URI_SCHEME_BOLT_SECURE,
            URI_SCHEME_NEO4J,
            URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE,
            URI_SCHEME_NEO4J_SECURE,
        ]
        raise _ConfigurationError(
            f"URI scheme {scheme!r} is not supported. "
            f"Supported URI schemes are {supported_schemes}. "
            "Examples: bolt://host[:port] or "
            "neo4j://host[:port][?routing_context]"
        )

    return driver_type, security_type


def parse_routing_context(query):
    """
    Parse the query portion of a URI.

    Generates a routing context dictionary.
    """
    if not query:
        return {}

    context = {}
    parameters = parse_qs(query, True)
    for key in parameters:
        value_list = parameters[key]
        if len(value_list) != 1:
            raise _ConfigurationError(
                f"Duplicated query parameters with key '{key}', value "
                f"'{value_list}' found in query string '{query}'"
            )
        value = value_list[0]
        if not value:
            raise _ConfigurationError(
                f"Invalid parameters:'{key}={value}' in query string "
                f"'{query}'."
            )
        context[key] = value

    return context
