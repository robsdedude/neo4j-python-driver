# Copyright (c) "Neo4j"
# Neo4j Sweden AB [https://neo4j.com]
#
# This file is part of Neo4j.
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

""" Base classes and helpers.
"""

from ._api import (
    Auth,
    AuthToken as _AuthToken,
    basic_auth,
    bearer_auth,
    Bookmark,
    Bookmarks,
    check_access_mode as _check_access_mode,
    custom_auth,
    DEFAULT_DATABASE,
    DRIVER_BOLT as _DRIVER_BOLT,
    DRIVER_NEO4J as _DRIVER_NEO4J,
    kerberos_auth,
    parse_neo4j_uri as _parse_neo4j_uri,
    parse_routing_context as _parse_routing_context,
    READ_ACCESS,
    SECURITY_TYPE_NOT_SECURE as _SECURITY_TYPE_NOT_SECURE,
    SECURITY_TYPE_SECURE as _SECURITY_TYPE_SECURE,
    SECURITY_TYPE_SELF_SIGNED_CERTIFICATE as _SECURITY_TYPE_SELF_SIGNED_CERTIFICATE,
    ServerInfo,
    SYSTEM_DATABASE,
    TRUST_ALL_CERTIFICATES,
    TRUST_SYSTEM_CA_SIGNED_CERTIFICATES,
    URI_SCHEME_BOLT,
    URI_SCHEME_BOLT_ROUTING as _URI_SCHEME_BOLT_ROUTING,
    URI_SCHEME_BOLT_SECURE,
    URI_SCHEME_BOLT_SELF_SIGNED_CERTIFICATE,
    URI_SCHEME_NEO4J,
    URI_SCHEME_NEO4J_SECURE,
    URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE,
    Version,
    WRITE_ACCESS,
)


__all__ = [
    "READ_ACCESS",
    "WRITE_ACCESS",
    "CLUSTER_AUTO_ACCESS",
    "CLUSTER_READERS_ACCESS",
    "CLUSTER_WRITERS_ACCESS",
    "DRIVER_BOLT",
    "DRIVER_NEO4J",
    "SECURITY_TYPE_NOT_SECURE",
    "SECURITY_TYPE_SELF_SIGNED_CERTIFICATE",
    "SECURITY_TYPE_SECURE",
    "URI_SCHEME_BOLT",
    "URI_SCHEME_BOLT_SELF_SIGNED_CERTIFICATE",
    "URI_SCHEME_BOLT_SECURE",
    "URI_SCHEME_NEO4J",
    "URI_SCHEME_NEO4J_SELF_SIGNED_CERTIFICATE",
    "URI_SCHEME_NEO4J_SECURE",
    "URI_SCHEME_BOLT_ROUTING",
    "SYSTEM_DATABASE",
    "DEFAULT_DATABASE",
    "TRUST_SYSTEM_CA_SIGNED_CERTIFICATES",
    "TRUST_ALL_CERTIFICATES",
    "Auth",
    "AuthToken",
    "basic_auth",
    "kerberos_auth",
    "bearer_auth",
    "custom_auth",
    "Bookmark",
    "Bookmarks",
    "ServerInfo",
    "Version",
    "parse_neo4j_uri",
    "check_access_mode",
    "parse_routing_context",
]


def __getattr__(name):
    # TODO 6.0 - remove this
    deprecations_with_replacement = {
        "AuthToken": "Auth"
    }
    if name in deprecations_with_replacement:
        new_name = deprecations_with_replacement[name]
        from ._meta import deprecation_warn
        deprecation_warn(
            f"{name} has been deprecated in favor of {new_name}.",
            stack_level=2
        )
        return globals()[f"_{name}"]
    if name in (
        "DRIVER_BOLT", "DRIVER_NEO4J", "SECURITY_TYPE_NOT_SECURE",
        "SECURITY_TYPE_SELF_SIGNED_CERTIFICATE", "SECURITY_TYPE_SECURE",
        "URI_SCHEME_BOLT_ROUTING", "parse_neo4j_uri", "check_access_mode",
        "parse_routing_context"
    ):
        from ._meta import deprecation_warn
        deprecation_warn(
            "Importing {} from neo4j.api is deprecated without replacement."
            "It's internal and will be removed in a future version."
            .format(name),
            stack_level=2
        )
        return globals()[f"_{name}"]
    raise AttributeError(f"module {__name__} has no attribute {name}")
