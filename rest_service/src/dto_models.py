# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2021, Lucina
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from __future__ import annotations

__all__: list[str] = [
    "UndefinedType",
    "UNDEFINED",
    "UndefinedOr",
    "BasicError",
    "AuthUser",
    "LinkAuth",
    "Device",
    "ReceivedMessage",
    "ReceivedMessageUpdate",
    "Message",
    "File",
    "View",
    "BASIC_ERROR",
    "LINK_AUTH_RESPONSE",
    "USER_AUTH_RESPONSE",
]

import datetime
import inspect
import typing
import uuid

import pydantic

from . import flags
from . import validation

if typing.TYPE_CHECKING:
    import collections.abc as collections

    from . import utilities


class UndefinedType:
    __instance: typing.Optional[UndefinedType] = None

    def __new__(cls) -> UndefinedType:
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)

        return cls.__instance

    def __bool__(self) -> typing.Literal[False]:
        return False

    def __copy__(self) -> UndefinedType:
        return self

    def __deepcopy__(self, memo: collections.MutableMapping[int, typing.Any]) -> UndefinedType:
        memo[id(self)] = self

        return self

    def __getstate__(self) -> typing.Any:
        return False

    def __reduce__(self) -> str:
        return "UNDEFINED"


_ValueT = typing.TypeVar("_ValueT")
UNDEFINED = UndefinedType()
UndefinedOr = typing.Union[UndefinedType, _ValueT]


class _ModelConfig(pydantic.BaseConfig):
    orm_mode = True
    use_enum_values = True


class BasicError(pydantic.BaseModel):
    detail: str

    Config = _ModelConfig


class AuthUser(pydantic.BaseModel):
    created_at: datetime.datetime
    flags: flags.UserFlags
    id: uuid.UUID
    username: str

    Config = _ModelConfig


class LinkAuth(pydantic.BaseModel):
    access: int  # TODO: flags?
    expires_at: typing.Optional[datetime.datetime]
    message_id: uuid.UUID
    resource: typing.Optional[str]
    token: str


class Device(pydantic.BaseModel):
    is_required_viewer: bool
    name: str = pydantic.Field(
        ..., min_length=validation.MINIMUM_NAME_LENGTH, max_length=validation.MAXIMUM_NAME_LENGTH
    )

    Config = _ModelConfig


if typing.TYPE_CHECKING:

    class ReceivedDeviceUpdate(pydantic.BaseModel):
        is_required_viewer: UndefinedOr[bool]
        name: UndefinedOr[str]


else:
    # We can't type this as undefinable at runtime as this breaks FastAPI's handling.
    class ReceivedDeviceUpdate(pydantic.BaseModel):
        is_required_viewer: bool = pydantic.Field(default_factory=UndefinedType)
        name: str = pydantic.Field(
            default_factory=UndefinedType,
            min_length=validation.MINIMUM_NAME_LENGTH,
            max_length=validation.MAXIMUM_NAME_LENGTH,
        )

        Config = _ModelConfig


class ReceivedMessage(pydantic.BaseModel):
    expire_after: typing.Optional[datetime.timedelta] = None
    is_transient: bool = True
    text: typing.Optional[str] = None
    title: typing.Optional[str] = None

    Config = _ModelConfig

    @pydantic.validator("expire_after")
    def validate_expire_after(
        cls, expire_after_: typing.Optional[datetime.timedelta]
    ) -> typing.Optional[datetime.timedelta]:
        return validation.validate_timedelta(expire_after_) if expire_after_ is not None else None


if typing.TYPE_CHECKING:

    class ReceivedMessageUpdate(pydantic.BaseModel):
        expire_after: typing.Union[datetime.timedelta, UndefinedType, None]
        is_transient: UndefinedOr[bool]
        text: typing.Union[str, UndefinedType, None]
        title: typing.Union[str, UndefinedType, None]


else:

    # We can't type this as undefinable at runtime as this breaks FastAPI's handling.
    class ReceivedMessageUpdate(pydantic.BaseModel):
        expire_after: typing.Optional[datetime.timedelta] = pydantic.Field(default_factory=UndefinedType)
        is_transient: bool = pydantic.Field(default_factory=UndefinedType)
        text: typing.Optional[str] = pydantic.Field(default_factory=UndefinedType)
        title: typing.Optional[str] = pydantic.Field(default_factory=UndefinedType)

        Config = _ModelConfig

        @pydantic.validator("expire_after")
        def validate_expire_after(
            cls, expire_after_: typing.Optional[datetime.timedelta]
        ) -> typing.Optional[datetime.timedelta]:
            return validation.validate_timedelta(expire_after_) if expire_after_ is not None else None


class Message(pydantic.BaseModel):
    id: uuid.UUID
    created_at: datetime.datetime
    expire_at: typing.Union[datetime.datetime, None]
    is_transient: bool
    private_link: str = pydantic.Field(default="")  # This field should be filled in before this is sent.
    shareable_link: str = pydantic.Field(default="")  # This field should be filled in before this is sent.
    text: typing.Optional[str]
    title: typing.Optional[str]
    files: list[File] = pydantic.Field(default_factory=list)

    Config = _ModelConfig

    def with_paths(self, metadata: utilities.Metadata, *, recursive: bool = True) -> None:
        self.private_link = metadata.message_private_uri(self.id)
        self.shareable_link = metadata.message_public_uri(self.id)

        if recursive:
            for file in self.files:
                file.with_paths(metadata)


class File(pydantic.BaseModel):
    content_type: str
    file_name: str
    message_id: uuid.UUID
    private_link: str = pydantic.Field(default="")  # This field should be filled in before this is sent.
    shareable_link: str = pydantic.Field(default="")  # This field should be filled in before this is sent.
    set_at: datetime.datetime

    Config = _ModelConfig

    def with_paths(self, metadata: utilities.Metadata) -> None:
        self.private_link = metadata.file_private_uri(self.message_id, self.file_name)
        self.shareable_link = metadata.file_public_uri(self.message_id, self.file_name)


class View(pydantic.BaseModel):
    created_at: datetime.datetime
    device_name: str = pydantic.Field(default="")  # This field should be filled in before this is sent.
    message_id: uuid.UUID

    Config = _ModelConfig


# TODO: switch to func which accepts description
BASIC_ERROR: typing.Final[dict[str, typing.Any]] = {"model": BasicError}
LINK_AUTH_RESPONSE: typing.Final[dict[typing.Union[int, str], typing.Any]] = {
    401: {**BASIC_ERROR, "description": "Returned when an invalid link token was provided."}
}
USER_AUTH_RESPONSE: typing.Final[dict[typing.Union[int, str], typing.Any]] = {
    401: {**BASIC_ERROR, "description": "Returned when invalid user authorization was provided."}
}


if not typing.TYPE_CHECKING:
    for entry in globals().copy().values():
        if inspect.isclass(entry) and issubclass(entry, pydantic.BaseModel):
            entry.update_forward_refs()

    del entry
