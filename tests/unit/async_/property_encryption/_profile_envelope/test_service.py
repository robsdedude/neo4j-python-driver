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

import base64

import pytest

from neo4j import _typing as t
from neo4j._async.property_encryption.profile_envelope._service import (
    _AsyncLocalKeyEncapsulationService,
    AsyncKeyEncapsulationServices,
)
from neo4j._property_encryption.profile_envelope import KeyEncapsulationOptions
from neo4j.warnings import PreviewWarning

from ....._async_compat import mark_async_test
from ....._optional_deps import mark_skip_if_crypto_dependencies_missing


if t.TYPE_CHECKING:
    from pytest_mock import MockFixture


MASTER_KEY = bytes(range(32))
MASTER_KEY2 = bytes(range(32, 64))


@pytest.fixture
def service() -> _AsyncLocalKeyEncapsulationService:
    return _AsyncLocalKeyEncapsulationService(MASTER_KEY)


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_local_factory(mocker: MockFixture) -> None:
    original_init = _AsyncLocalKeyEncapsulationService.__init__
    init_mock = mocker.patch.object(
        _AsyncLocalKeyEncapsulationService,
        "__init__",
        autospec=True,
        wraps=original_init,
    )

    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        service = AsyncKeyEncapsulationServices.local(MASTER_KEY)

    assert isinstance(service, _AsyncLocalKeyEncapsulationService)
    init_mock.assert_called_once_with(service, MASTER_KEY)


@pytest.mark.parametrize(
    ("master_key", "expected_error", "expected_message"),
    (
        pytest.param(
            None,
            TypeError,
            r"key\b.*\bbytes",
            id="none",
        ),
        pytest.param(
            "0" * 32,
            TypeError,
            r"key\b.*\bbytes",
            id="str",
        ),
        pytest.param(
            32,
            TypeError,
            r"key\b.*\bbytes",
            id="int",
        ),
        *(
            pytest.param(
                bytes(length),
                ValueError,
                r"\bkey\b.*\bsize\b",
                id=f"{length}-bytes",
            )
            for length in (0, 1, 16, 24, 31, 33, 64, 128, 255, 256, 512)
        ),
    ),
)
@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_local_factory_invalid_key(
    master_key: t.Any,
    expected_error: type[Exception],
    expected_message: str,
) -> None:
    with (
        pytest.raises(expected_error, match=expected_message),
        pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"),
    ):
        AsyncKeyEncapsulationServices.local(master_key)


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_encapsulate(
    service: _AsyncLocalKeyEncapsulationService, mocker: MockFixture
) -> None:
    iv = bytes(range(16))
    secret_key = bytes(range(32, 64))
    urandom = mocker.patch(
        "neo4j._async.property_encryption.profile_envelope._service"
        ".os.urandom",
        side_effect=(iv, secret_key),
    )

    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        result = await service.encapsulate(None)

    assert result.secret_key == secret_key
    assert result.metadata == {"iv": base64.b64encode(iv).decode("utf-8")}
    # AES-GCM appends no padding, but requires a 16-byte authentication tag.
    assert len(result.encapsulation) == len(secret_key) + 16
    assert result.encapsulation[: len(secret_key)] != secret_key
    assert urandom.call_args_list == [mocker.call(16), mocker.call(32)]


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_encapsulate_rejects_options(
    service: _AsyncLocalKeyEncapsulationService,
) -> None:
    options = t.cast(KeyEncapsulationOptions, object())

    with pytest.raises(ValueError) as exc_info:
        await service.encapsulate(options)

    assert str(exc_info.value) == (
        "Local key encapsulation service does not accept options."
    )


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_encapsulate_decapsulate_round_trip(
    service: _AsyncLocalKeyEncapsulationService,
) -> None:
    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        result = await service.encapsulate(None)

    secret_key = await service.decapsulate(
        result.encapsulation, result.metadata
    )

    assert secret_key == result.secret_key


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_decapsulate_requires_iv(
    service: _AsyncLocalKeyEncapsulationService,
) -> None:
    with pytest.raises(ValueError) as exc_info:
        await service.decapsulate(b"encapsulated key", {})

    assert (
        str(exc_info.value) == "Metadata for decapsulation must contain 'iv'."
    )
    assert isinstance(exc_info.value.__cause__, KeyError)
    assert exc_info.value.__cause__.args == ("iv",)


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_decapsulate_rejects_extra_metadata(
    service: _AsyncLocalKeyEncapsulationService,
) -> None:
    metadata = {
        "iv": base64.b64encode(bytes(16)).decode("utf-8"),
        "extra": "metadata",
    }

    with pytest.raises(ValueError) as exc_info:
        await service.decapsulate(b"encapsulated key", metadata)

    assert str(exc_info.value) == (
        "Metadata for decapsulation must only contain 'iv'."
    )
    assert exc_info.value.__cause__ is None


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_decapsulate_rejects_invalid_base64_iv(
    service: _AsyncLocalKeyEncapsulationService,
) -> None:
    with pytest.raises(ValueError) as exc_info:
        await service.decapsulate(b"encapsulated key", {"iv": "not base64"})

    assert str(exc_info.value) == (
        "Metadata for decapsulation must contain a valid base64-encoded 'iv'."
    )
    assert exc_info.value.__cause__ is not None


@pytest.mark.parametrize("iv_length", (0, 15, 17))
@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_decapsulate_rejects_invalid_iv_length(
    service: _AsyncLocalKeyEncapsulationService, iv_length: int
) -> None:
    iv_base64 = base64.b64encode(bytes(iv_length)).decode("utf-8")

    with pytest.raises(ValueError) as exc_info:
        await service.decapsulate(b"encapsulated key", {"iv": iv_base64})

    assert str(exc_info.value) == (
        "Metadata for decapsulation must contain a valid 16-byte 'iv'."
    )
    assert exc_info.value.__cause__ is None


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_decapsulate_rejects_tampered_encapsulation(
    service: _AsyncLocalKeyEncapsulationService,
) -> None:
    from cryptography.exceptions import InvalidTag

    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        result = await service.encapsulate(None)
    tampered = bytes([result.encapsulation[0] ^ 1]) + result.encapsulation[1:]

    with pytest.raises(ValueError) as exc_info:
        await service.decapsulate(tampered, result.metadata)

    assert str(exc_info.value) == "Failed to decapsulate the key."
    assert isinstance(exc_info.value.__cause__, InvalidTag)


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_key_roundtrip() -> None:
    service1 = _AsyncLocalKeyEncapsulationService(MASTER_KEY)
    service2 = _AsyncLocalKeyEncapsulationService(MASTER_KEY)

    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        result = await service1.encapsulate(None)
    secret_key = await service2.decapsulate(
        result.encapsulation, result.metadata
    )

    assert secret_key == result.secret_key


@mark_skip_if_crypto_dependencies_missing
@mark_async_test
async def test_key_roundtrip_with_wrong_key() -> None:
    from cryptography.exceptions import InvalidTag

    service1 = _AsyncLocalKeyEncapsulationService(MASTER_KEY)
    service2 = _AsyncLocalKeyEncapsulationService(MASTER_KEY2)

    with pytest.warns(PreviewWarning, match=r"\bProperty encryption\b"):
        result = await service1.encapsulate(None)

    with pytest.raises(ValueError) as exc_info:
        await service2.decapsulate(result.encapsulation, result.metadata)

    assert str(exc_info.value) == "Failed to decapsulate the key."
    assert isinstance(exc_info.value.__cause__, InvalidTag)
