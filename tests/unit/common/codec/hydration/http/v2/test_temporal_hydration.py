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

import pytest
import pytz

from neo4j._codec.hydration import BrokenHydrationObject
from neo4j._codec.hydration.http.v2 import HydrationHandler
from neo4j.time import (
    Date,
    DateTime,
    Duration,
    Time,
)

from .._base import HydrationHandlerTestBase


if t.TYPE_CHECKING:
    from neo4j._codec.hydration.http._common import HydrationScopeHttp


class TestTemporalHydration(HydrationHandlerTestBase):
    @pytest.fixture
    def hydration_handler(self) -> HydrationHandler:
        return HydrationHandler()

    def test_hydrate_date(self, hydration_scope: HydrationScopeHttp) -> None:
        encoded = {
            "$type": "Date",
            "_value": "1991-08-24",
        }
        d = hydration_scope.hydration_hooks[type(encoded)](encoded)
        assert isinstance(d, Date)
        assert d.year == 1991
        assert d.month == 8
        assert d.day == 24

    def test_hydrate_time(self, hydration_scope: HydrationScopeHttp) -> None:
        encoded = {
            "$type": "Time",
            "_value": "01:02:03.000000004+01:00",
        }
        t = hydration_scope.hydration_hooks[type(encoded)](encoded)
        assert isinstance(t, Time)
        assert t.hour == 1
        assert t.minute == 2
        assert t.second == 3
        assert t.nanosecond == 4
        assert t.tzinfo == pytz.FixedOffset(60)

    def test_hydrate_local_time(
        self, hydration_scope: HydrationScopeHttp
    ) -> None:
        encoded = {
            "$type": "LocalTime",
            "_value": "01:02:03.000000004",
        }
        t = hydration_scope.hydration_hooks[type(encoded)](encoded)
        assert isinstance(t, Time)
        assert t.hour == 1
        assert t.minute == 2
        assert t.second == 3
        assert t.nanosecond == 4
        assert t.tzinfo is None

    def test_hydrate_date_time(
        self, hydration_scope: HydrationScopeHttp
    ) -> None:
        encoded = {
            "$type": "OffsetDateTime",
            "_value": "2018-10-12T11:37:41.474716862+01:00",
        }
        dt = hydration_scope.hydration_hooks[type(encoded)](encoded)
        assert isinstance(dt, DateTime)
        assert dt.year == 2018
        assert dt.month == 10
        assert dt.day == 12
        assert dt.hour == 11
        assert dt.minute == 37
        assert dt.second == 41
        assert dt.nanosecond == 474716862
        assert dt.tzinfo == pytz.FixedOffset(60)

    @pytest.mark.parametrize(
        "value",
        (
            "2018-10-12T13:37:41.474716862+02:00[Europe/Stockholm]",
            "2018-10-12T12:37:41.474716862+01:00[Europe/Stockholm]",
            "2018-10-12T11:37:41.474716862Z[Europe/Stockholm]",
            "2018-10-11T23:37:41.474716862-12:00[Europe/Stockholm]",
        ),
    )
    def test_hydrate_date_time_zone_id(
        self, hydration_scope: HydrationScopeHttp, value: str
    ) -> None:
        encoded = {
            "$type": "OffsetDateTime",
            "_value": value,
        }
        dt = hydration_scope.hydration_hooks[type(encoded)](encoded)
        assert isinstance(dt, DateTime)
        assert dt.year == 2018
        assert dt.month == 10
        assert dt.day == 12
        assert dt.hour == 13
        assert dt.minute == 37
        assert dt.second == 41
        assert dt.nanosecond == 474716862
        tz = (
            pytz.timezone("Europe/Stockholm")
            .localize(dt.replace(tzinfo=None))
            .tzinfo
        )
        assert dt.tzinfo == tz

    def test_hydrate_date_time_unknown_zone_id(
        self, hydration_scope: HydrationScopeHttp
    ) -> None:
        encoded = {
            "$type": "OffsetDateTime",
            "_value": "2018-10-12T11:37:41.474716862Z[Europe/Neo4j]",
        }
        res = hydration_scope.hydration_hooks[type(encoded)](encoded)
        assert isinstance(res, BrokenHydrationObject)
        exc = None
        try:
            pytz.timezone("Europe/Neo4j")
        except Exception as e:
            exc = e
        assert exc.__class__ == res.error.__class__
        assert str(exc) == str(res.error)

    def test_hydrate_local_date_time(
        self, hydration_scope: HydrationScopeHttp
    ) -> None:
        encoded = {
            "$type": "LocalDateTime",
            "_value": "2018-10-12T11:37:41.474716862",
        }
        dt = hydration_scope.hydration_hooks[type(encoded)](encoded)
        assert isinstance(dt, DateTime)
        assert dt.year == 2018
        assert dt.month == 10
        assert dt.day == 12
        assert dt.hour == 11
        assert dt.minute == 37
        assert dt.second == 41
        assert dt.nanosecond == 474716862
        assert dt.tzinfo is None

    def test_hydrate_duration(
        self, hydration_scope: HydrationScopeHttp
    ) -> None:
        encoded = {
            "$type": "Duration",
            "_value": "P1M2DT3.000000004S",
        }
        d = hydration_scope.hydration_hooks[type(encoded)](encoded)
        assert isinstance(d, Duration)
        assert d.months == 1
        assert d.days == 2
        assert d.seconds == 3
        assert d.nanoseconds == 4
