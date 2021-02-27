# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2021, Faster Speeding
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
    "ReceivedUser",
    "ReceivedUserUpdate",
    "User",
    "Device",
    "ReceivedMessage",
    "ReceivedMessageUpdate",
    "Message",
    "File",
    "Permission",
    "ReceivedView",
    "View",
    "BASIC_ERROR",
    "AUTH_RESPONSE",
]

import datetime
import typing

import pydantic

from . import flags
from . import validation

if typing.TYPE_CHECKING:
    import collections.abc as collections


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


class ReceivedUser(pydantic.BaseModel):
    flags: flags.UserFlags = pydantic.Field(ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT)
    username: str = pydantic.Field(
        min_length=validation.MINIMUM_NAME_LENGTH,
        max_length=validation.MAXIMUM_NAME_LENGTH,
        regex=validation.RAW_USERNAME_REGEX,  # We may be duping this check but this keeps the regex documented.
    )
    password: str = pydantic.Field(
        min_length=validation.MINIMUM_PASSWORD_LENGTH, max_length=validation.MAXIMUM_PASSWORD_LENGTH
    )

    Config = _ModelConfig

    # Pydantic's builtin regex matching only uses match as opposed to full match which is not the behaviour we want.
    @pydantic.validator("username")
    def validate_username(cls, username_: str) -> str:
        if validation.USERNAME_REGEX.fullmatch(username_):
            return username_

        raise ValueError(f"username does not match regex {validation.RAW_USERNAME_REGEX}")


if typing.TYPE_CHECKING:

    class ReceivedUserUpdate(pydantic.BaseModel):
        username: UndefinedOr[str]
        password: UndefinedOr[str]


else:

    # We can't type this as undefinable at runtime as this breaks FastAPI's handling.
    class ReceivedUserUpdate(pydantic.BaseModel):
        username: str = pydantic.Field(
            default_factory=UndefinedType,
            min_length=validation.MINIMUM_NAME_LENGTH,
            max_length=validation.MAXIMUM_NAME_LENGTH,
            regex=validation.RAW_USERNAME_REGEX,  # We may be duping this check but this keeps the regex documented.
        )
        password: str = pydantic.Field(
            default_factory=UndefinedType,
            min_length=validation.MINIMUM_PASSWORD_LENGTH,
            max_length=validation.MAXIMUM_PASSWORD_LENGTH,
        )

        Config = _ModelConfig

        # Pydantic's builtin regex matching only uses match as opposed to full match which is not the behaviour we want.
        @pydantic.validator("username")
        def validate_username(cls, username_: str) -> str:
            if validation.USERNAME_REGEX.fullmatch(username_):
                return username_

            raise ValueError(f"username does not match regex {validation.RAW_USERNAME_REGEX}")


class User(pydantic.BaseModel):
    id: int
    created_at: datetime.datetime
    flags: flags.UserFlags
    username: str

    Config = _ModelConfig

    def __int__(self) -> int:
        return self.id


class Device(pydantic.BaseModel):
    access: flags.DeviceAccessLevel = pydantic.Field(ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT)
    is_required_viewer: bool
    name: str = pydantic.Field(
        ..., min_length=validation.MINIMUM_NAME_LENGTH, max_length=validation.MAXIMUM_NAME_LENGTH
    )

    Config = _ModelConfig


if typing.TYPE_CHECKING:

    class ReceivedDeviceUpdate(pydantic.BaseModel):
        access: UndefinedOr[flags.DeviceAccessLevel]
        is_required_viewer: UndefinedOr[bool]
        name: UndefinedOr[str]


else:
    # We can't type this as undefinable at runtime as this breaks FastAPI's handling.
    class ReceivedDeviceUpdate(pydantic.BaseModel):
        access: flags.DeviceAccessLevel = pydantic.Field(
            default_factory=UndefinedType, ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT
        )
        is_required_viewer: bool = pydantic.Field(default_factory=UndefinedType)
        name: str = pydantic.Field(
            default_factory=UndefinedType,
            min_length=validation.MINIMUM_NAME_LENGTH,
            max_length=validation.MAXIMUM_NAME_LENGTH,
        )

        Config = _ModelConfig


class ReceivedMessage(pydantic.BaseModel):
    expire_after: typing.Optional[datetime.timedelta] = None
    is_public: bool = False
    is_transient: bool = True
    text: typing.Optional[str] = None
    title: typing.Optional[str] = None

    Config = _ModelConfig

    @pydantic.validator("expire_after")
    def validate_expire_after(cls, expire_after_: datetime.timedelta) -> datetime.timedelta:
        if expire_after_ > validation.MINIMUM_TIMEDELTA:
            return expire_after_

        minimum = validation.MINIMUM_TIMEDELTA.total_seconds()
        raise ValueError(f"expire_after must be greater than or equal to {minimum} seconds")


if typing.TYPE_CHECKING:

    class ReceivedMessageUpdate(pydantic.BaseModel):
        expire_after: typing.Union[datetime.timedelta, UndefinedType, None]
        is_public: UndefinedOr[bool]
        is_transient: UndefinedOr[bool]
        text: typing.Union[str, UndefinedType, None]
        title: typing.Union[str, UndefinedType, None]


else:

    # We can't type this as undefinable at runtime as this breaks FastAPI's handling.
    class ReceivedMessageUpdate(pydantic.BaseModel):
        expire_after: typing.Optional[datetime.timedelta] = pydantic.Field(default_factory=UndefinedType)
        is_public: bool = pydantic.Field(default_factory=UndefinedType)
        is_transient: bool = pydantic.Field(default_factory=UndefinedType)
        text: typing.Optional[str] = pydantic.Field(default_factory=UndefinedType)
        title: typing.Optional[str] = pydantic.Field(default_factory=UndefinedType)

        Config = _ModelConfig

        @pydantic.validator("expire_after")
        def validate_expire_after(cls, expire_after_: datetime.timedelta) -> datetime.timedelta:
            if expire_after_ > validation.MINIMUM_TIMEDELTA:
                return expire_after_

            minimum = validation.MINIMUM_TIMEDELTA.total_seconds()
            raise ValueError(f"expire_after must be greater than or equal to {minimum} seconds")


class Message(pydantic.BaseModel):
    id: int
    created_at: datetime.datetime
    expire_at: typing.Union[datetime.datetime, None]
    is_public: bool
    is_transient: bool
    text: typing.Optional[str]
    title: typing.Optional[str]
    user_id: int

    Config = _ModelConfig

    def __int__(self) -> int:
        return self.id


class File(pydantic.BaseModel):
    id: int = pydantic.Field(ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT)
    file_name: str
    message_id: int = pydantic.Field(ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT)

    Config = _ModelConfig

    def __int__(self) -> int:
        return self.id


class Permission(pydantic.BaseModel):
    message_id: int = pydantic.Field(ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT)
    permissions: flags.PermissionFlags = pydantic.Field(ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT)
    user_id: int = pydantic.Field(ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT)

    Config = _ModelConfig


class ReceivedView(pydantic.BaseModel):
    device_id: int = pydantic.Field(ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT)
    message_id: int = pydantic.Field(ge=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT)

    Config = _ModelConfig


class View(ReceivedView, pydantic.BaseModel):
    created_at: datetime.datetime


BASIC_ERROR: typing.Final[dict[str, typing.Any]] = {"model": BasicError}
AUTH_RESPONSE: typing.Final[dict[typing.Union[int, str], typing.Any]] = {
    401: {**BASIC_ERROR, "description": "Returned when invalid user authorization was provided."}
}
