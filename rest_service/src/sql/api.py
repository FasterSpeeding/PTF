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

__all__: list[str] = ["DatabaseHandler", "DatabaseIterator", "DatabaseManager", "FilteredClear"]

import abc
import typing
from typing import Literal

if typing.TYPE_CHECKING:
    import asyncio
    import collections.abc as collections
    import datetime
    import uuid

    from . import dao_protos

    _DatabaseT = typing.TypeVar("_DatabaseT", bound="DatabaseHandler")
    _OtherValueT = typing.TypeVar("_OtherValueT")
    _DatabaseCollectionT = typing.TypeVar("_DatabaseCollectionT", bound="DatabaseCollection[typing.Any, typing.Any]")

_ValueT_co = typing.TypeVar("_ValueT_co", covariant=True)
_FieldT_co = typing.TypeVar("_FieldT_co", bound=str, contravariant=True)

FilterTypeT = typing.Union[
    Literal["lt"],
    Literal["le"],
    Literal["eq"],
    Literal["ne"],
    Literal["ge"],
    Literal["gt"],
    Literal["contains"],
]
# For a reference on what these all mean see https://docs.python.org/3/library/operator.html

UserFieldsT = typing.Union[
    Literal["id"], Literal["created_at"], Literal["flags"], Literal["password_hash"], Literal["username"]
]
DeviceFieldsT = typing.Union[Literal["id"], Literal["is_required_viewer"], Literal["name"], Literal["user_id"]]
MessageFieldsT = typing.Union[
    Literal["id"],
    Literal["created_at"],
    Literal["expire_at"],
    Literal["is_transient"],
    Literal["text"],
    Literal["title"],
    Literal["user_id"],
]
FileFieldsT = typing.Union[Literal["content_type"], Literal["file_name"], Literal["message_id"], Literal["set_at"]]
ViewFieldsT = typing.Union[Literal["created_at"], Literal["device_id"], Literal["message_id"]]


class SQLError(Exception):
    __slots__: tuple[str, ...] = ("message",)

    def __init__(self, message: str, /) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message


# TODO: make abstract
# TODO: Remove this as we shouldn't be expecting sql to raise anything other than field already exists errors
# as validation should catch other stuff
class DataError(SQLError):
    __slots__: tuple[str, ...] = ()


class AlreadyExistsError(SQLError):
    __slots__: tuple[str, ...] = ()


class DatabaseCollection(typing.Protocol[_FieldT_co, _ValueT_co]):
    __slots__: tuple[str, ...] = ()

    async def collect(self) -> collections.Collection[_ValueT_co]:
        raise NotImplementedError

    async def count(self) -> int:
        raise NotImplementedError

    def filter(
        self: _DatabaseCollectionT, filter_type: FilterTypeT, *rules: tuple[_FieldT_co, typing.Any]
    ) -> _DatabaseCollectionT:
        raise NotImplementedError

    def filter_truth(self: _DatabaseCollectionT, *fields: _FieldT_co, truth: bool = True) -> _DatabaseCollectionT:
        raise NotImplementedError

    async def iter(self) -> collections.Iterator[_ValueT_co]:
        raise NotImplementedError

    def limit(self: _DatabaseCollectionT, limit: int, /) -> _DatabaseCollectionT:
        raise NotImplementedError

    # TODO: do we want to finalise here?
    async def map(self, cast: typing.Callable[[_ValueT_co], _OtherValueT], /) -> collections.Iterator[_OtherValueT]:
        raise NotImplementedError

    def order_by(self: _DatabaseCollectionT, field: _FieldT_co, /, ascending: bool = True) -> _DatabaseCollectionT:
        raise NotImplementedError


class DatabaseIterator(DatabaseCollection[_FieldT_co, _ValueT_co], typing.Protocol[_FieldT_co, _ValueT_co]):
    __slots__: tuple[str, ...] = ()

    def __await__(self) -> collections.Generator[typing.Any, None, collections.Iterable[_ValueT_co]]:
        raise NotImplementedError


class FilteredClear(DatabaseCollection[_FieldT_co, _ValueT_co], typing.Protocol[_FieldT_co, _ValueT_co]):
    __slots__: tuple[str, ...] = ()

    def __await__(self) -> collections.Generator[typing.Any, None, int]:
        raise NotImplementedError

    async def execute(self) -> int:
        raise NotImplementedError

    def start(self) -> asyncio.Task[int]:
        raise NotImplementedError


class DatabaseHandler(abc.ABC):
    __slots__: tuple[str, ...] = ()

    @abc.abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def from_config(cls: type[_DatabaseT], config: collections.Mapping[str, typing.Any], /) -> _DatabaseT:
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def from_string(cls: type[_DatabaseT], url: str, /) -> _DatabaseT:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_user_by_id(self, user_id: uuid.UUID, /) -> typing.Optional[dao_protos.User]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_user_by_username(self, username: str, /) -> typing.Optional[dao_protos.User]:
        raise NotImplementedError

    @abc.abstractmethod
    def iter_users(self) -> DatabaseIterator[UserFieldsT, dao_protos.User]:
        raise NotImplementedError

    @abc.abstractmethod
    def clear_devices(self) -> FilteredClear[DeviceFieldsT, dao_protos.Device]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_device_by_id(self, device_id: int, /) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_device_by_name(self, user_id: uuid.UUID, device_name: str, /) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_device_by_id(self, device_id: int, /) -> typing.Optional[dao_protos.Device]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_device_by_name(self, user_id: uuid.UUID, device_name: str, /) -> typing.Optional[dao_protos.Device]:
        raise NotImplementedError

    @abc.abstractmethod
    def iter_devices(self) -> DatabaseIterator[DeviceFieldsT, dao_protos.Device]:
        raise NotImplementedError

    @abc.abstractmethod
    async def set_device(self, *, is_required_viewer: bool, user_id: uuid.UUID, name: str) -> dao_protos.Device:
        raise NotImplementedError

    @abc.abstractmethod
    async def update_device_by_id(
        self,
        device_id: int,
        /,
        *,
        is_required_viewer: bool = ...,
        name: str = ...,
    ) -> typing.Optional[dao_protos.Device]:
        raise NotImplementedError

    @abc.abstractmethod
    async def update_device_by_name(
        self,
        user_id: uuid.UUID,
        device_name: str,
        /,
        *,
        is_required_viewer: bool = ...,
        name: str = ...,
    ) -> typing.Optional[dao_protos.Device]:
        raise NotImplementedError

    @abc.abstractmethod
    def clear_messages(self) -> FilteredClear[MessageFieldsT, dao_protos.Message]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_message(self, message_id: uuid.UUID, user_id: typing.Optional[uuid.UUID] = None, /) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_message(
        self, message_id: uuid.UUID, user_id: typing.Optional[uuid.UUID] = None, /
    ) -> typing.Optional[dao_protos.Message]:
        raise NotImplementedError

    @abc.abstractmethod
    def iter_messages(self) -> DatabaseIterator[MessageFieldsT, dao_protos.Message]:
        raise NotImplementedError

    @abc.abstractmethod
    async def set_message(
        self,
        *,
        expire_at: typing.Optional[datetime.datetime],
        is_transient: bool,
        text: typing.Optional[str],
        title: typing.Optional[str],
        user_id: uuid.UUID,
    ) -> dao_protos.Message:
        raise NotImplementedError

    @abc.abstractmethod
    async def update_message(
        self,
        message_id: uuid.UUID,
        user_id: typing.Optional[uuid.UUID] = None,
        /,
        *,
        expire_at: typing.Optional[datetime.datetime] = ...,
        is_transient: bool = ...,
        text: typing.Optional[str] = ...,
        title: typing.Optional[str] = ...,
    ) -> typing.Optional[dao_protos.Message]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_file(self, message_id: uuid.UUID, file_name: str, /) -> typing.Optional[dao_protos.File]:
        raise NotImplementedError

    @abc.abstractmethod
    def iter_files(self) -> DatabaseIterator[FileFieldsT, dao_protos.File]:
        raise NotImplementedError

    @abc.abstractmethod
    def clear_views(self) -> FilteredClear[ViewFieldsT, dao_protos.View]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_view(self, device_id: int, message_id: uuid.UUID, /) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_view(self, device_id: int, message_id: uuid.UUID, /) -> typing.Optional[dao_protos.View]:
        raise NotImplementedError

    @abc.abstractmethod
    def iter_views(self) -> DatabaseIterator[ViewFieldsT, dao_protos.View]:
        raise NotImplementedError

    @abc.abstractmethod
    async def set_view(self, *, device_id: int, message_id: uuid.UUID) -> dao_protos.View:
        raise NotImplementedError


class DatabaseManager(typing.Protocol):
    __slots__: tuple[str, ...] = ("_database",)

    def __call__(self) -> DatabaseHandler:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError
