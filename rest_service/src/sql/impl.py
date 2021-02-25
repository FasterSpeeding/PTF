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

__all__: list[str] = ["DatabaseManager", "PostgreDatabase"]

import asyncio
import operator
import typing
import urllib.parse

# https://github.com/MagicStack/asyncpg/issues/699
import asyncpg.exceptions  # TODO: wait for asyncpg to add python 3.10 support
import sqlalchemy.exc
import sqlalchemy.ext.asyncio

from . import api
from . import dao_models
from . import dao_protos

if typing.TYPE_CHECKING:
    import collections.abc as collections
    import types

_DatabaseT = typing.TypeVar("_DatabaseT", bound=api.DatabaseHandler)
_SelfT = typing.TypeVar("_SelfT")
_ValueT = typing.TypeVar("_ValueT")
_FilterQueryT = typing.Union[sqlalchemy.sql.Select, sqlalchemy.sql.Delete]
_QueryT = typing.Union[_FilterQueryT, sqlalchemy.sql.Insert, sqlalchemy.sql.Update]


#  TODO: don't leak the schema?
class InsertErrorManager:
    __slots__: tuple[str, ...] = ()

    def __enter__(self) -> InsertErrorManager:
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[type[Exception]],
        exc_val: typing.Optional[Exception],
        exc_tb: typing.Optional[types.TracebackType],
    ) -> None:
        if exc_val is None:
            return None

        # These should really be caught earlier on by validation
        if isinstance(exc_val, sqlalchemy.exc.IntegrityError):
            if isinstance(exc_val.__cause__.__cause__, asyncpg.exceptions.IntegrityConstraintViolationError):
                raise api.DataError(str(exc_val.__cause__.__cause__.args[0]))

        elif isinstance(exc_val, sqlalchemy.exc.DBAPIError):
            if isinstance(exc_val.__cause__.__cause__, asyncpg.exceptions.DataError):
                raise api.DataError(str(exc_val.__cause__.__cause__.args[0]))


# Type error


_operators: dict[api.FilterTypeT, collections.Callable[..., typing.Any]] = {
    "lt": operator.lt,
    "le": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
    "ge": operator.ge,
    "gt": operator.gt,
}


def _filter(
    filter_type: api.FilterTypeT,
    query: _FilterQueryT,
    table: sqlalchemy.Table,
    rules: collections.Sequence[tuple[str, typing.Any]],
) -> _FilterQueryT:
    if filter_type == "contains":
        return query.filter(*(getattr(table.columns, attr).in_(value) for attr, value in rules))

    operator_ = _operators[filter_type]
    return query.filter(*(operator_(getattr(table.columns, attr), value) for attr, value in rules))


def _filter_truth(
    truth: bool, query: _FilterQueryT, table: sqlalchemy.Table, fields: collections.Sequence[str]
) -> _FilterQueryT:
    operator_ = operator.truth if truth else operator.not_
    return query.filter(*(operator_(getattr(table.columns, attr)) for attr in fields))


class PostgreIterator(api.DatabaseIterator[_ValueT]):
    __slots__: tuple[str, ...] = ("_engine", "_query", "_table")

    def __init__(
        self, engine: sqlalchemy.ext.asyncio.AsyncEngine, table: sqlalchemy.Table, query: sqlalchemy.sql.Select, /
    ) -> None:
        self._engine = engine
        self._query = query
        self._table = table

    # TODO: can we make this lazier and bring back this behaviour?
    # async def __anext__(self) -> _ValueT:
    #     if self._buffer is None:
    #         self._buffer = await self._fetch()
    #
    #     try:
    #         return self._buffer.pop(0)
    #
    #     except KeyError:
    #         raise StopAsyncIteration from None

    def __await__(self) -> collections.Generator[typing.Any, None, collections.Iterator[_ValueT]]:
        return self._fetch().__await__()

    # TODO: can we make this lazier?
    async def _fetch(self) -> collections.Iterator[_ValueT]:
        async with self._engine.begin() as connection:
            cursor = await connection.execute(self._query)
            return iter(cursor.fetchall())

    def filter(self, filter_type: api.FilterTypeT, *rules: tuple[str, typing.Any]) -> PostgreIterator[_ValueT]:
        self._query = _filter(filter_type, self._query, self._table, rules)
        return self

    def filter_truth(self, *fields: str, truth: bool = True) -> PostgreIterator[_ValueT]:
        self._query = _filter_truth(truth, self._query, self._table, fields)
        return self

    def limit(self, limit: int, /) -> PostgreIterator[_ValueT]:
        self._query = self._query.limit(limit)
        return self


class FilteredClear(api.FilteredClear[_ValueT]):
    __slots__: tuple[str, ...] = ("_engine", "_query", "_table")

    def __init__(
        self, engine: sqlalchemy.ext.asyncio.AsyncEngine, table: sqlalchemy.Table, query: sqlalchemy.sql.Delete, /
    ) -> None:
        self._engine = engine
        self._query = query
        self._table = table

    async def _await(self) -> int:
        async with self._engine.begin() as connection:
            cursor = await connection.execute(self._query)
            assert isinstance(cursor.rowcount, int)
            return cursor.rowcount

    def __await__(self) -> collections.Generator[typing.Any, None, int]:
        return self._await().__await__()

    async def collect(self) -> collections.Collection[_ValueT]:
        async with self._engine.begin() as connection:
            cursor = await connection.execute(self._query.returning(self._table))
            return typing.cast("collections.Collection[_ValueT]", cursor.fetchall())

    def filter(self, filter_type: api.FilterTypeT, *rules: tuple[str, typing.Any]) -> FilteredClear[_ValueT]:
        self._query = _filter(filter_type, self._query, self._table, rules)
        return self

    def filter_truth(self, *fields: str, truth: bool = True) -> FilteredClear[_ValueT]:
        self._query = _filter_truth(truth, self._query, self._table, fields)
        return self

    def start(self) -> asyncio.Task[int]:
        return asyncio.create_task(self._await())


class PostgreDatabase(api.DatabaseHandler):
    __slots__: tuple[str, ...] = ("_database",)

    def __init__(self, url: urllib.parse.SplitResult, /) -> None:
        engine_url = sqlalchemy.engine.URL.create(
            drivername=url.scheme,
            username=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port or 5432,
            database=url.path or "ptf",
            query=urllib.parse.parse_qs(url.query),
        )
        self._database: sqlalchemy.ext.asyncio.AsyncEngine = sqlalchemy.ext.asyncio.create_async_engine(
            engine_url, future=True
        )

    @classmethod
    def from_config(cls, config: collections.Mapping[str, typing.Any], /) -> PostgreDatabase:
        if "url" in config:
            return cls.from_string(config["url"])

        try:
            return cls.from_kwargs(
                database=str(config.get("database", "ptf")),
                host=str(config["host"]),
                username=str(config["username"]),
                port=int(config.get("port", 5432)),
                password=str(config["password"]),
            )

        except KeyError as exc:
            raise RuntimeError(f"Missing required config entry `{exc}`") from None

    @classmethod
    def from_kwargs(
        cls,
        password: str,
        host: str,
        username: str,
        database: str = "ptf",
        port: int = 5432,
        query: typing.Optional[collections.Mapping[str, typing.Union[str, collections.Sequence[str]]]] = None,
    ) -> PostgreDatabase:
        query = query or {}
        url = urllib.parse.SplitResult(
            "postgresql+asyncpg", f"{username}:{password}@{host}:{port}", database, urllib.parse.urlencode(query), ""
        )
        return cls(url)

    @classmethod
    def from_string(cls, url: str, /) -> PostgreDatabase:
        # This will be expected to roughly follow the format
        # "postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}" minus the scheme
        return cls(urllib.parse.urlsplit(url, scheme="postgresql+asyncpg"))

    async def close(self) -> None:
        await self._database.dispose()

    async def _execute(self, query: _QueryT) -> sqlalchemy.engine.cursor.CursorResult:
        async with self._database.begin() as connection:
            cursor = await connection.execute(query)
            return cursor

    async def _fetch_one(self, expected_type: type[_ValueT], query: sqlalchemy.sql.Select) -> typing.Optional[_ValueT]:
        cursor = await self._execute(query)
        result = cursor.fetchone()
        assert result is None or isinstance(result, expected_type)
        return result

    async def _fetch_all(
        self, expected_type: type[_ValueT], query: sqlalchemy.sql.Select
    ) -> collections.Sequence[_ValueT]:
        cursor = await self._execute(query)
        results = cursor.fetchall()

        if results:
            assert isinstance(results[1], expected_type)

        return typing.cast("collections.Sequence[_ValueT]", results)

    async def _set(self, expected_type: type[_ValueT], query: sqlalchemy.sql.Insert) -> _ValueT:
        with InsertErrorManager():
            cursor = await self._execute(query)
            result = cursor.fetchone()
            assert isinstance(result, expected_type)
            return result

    # TODO: what happens if you try to update en entry that doesn't exist
    async def _update(self, expected_type: type[_ValueT], query: sqlalchemy.sql.Update) -> typing.Optional[_ValueT]:
        async with self._database.begin() as connection:
            cursor = await connection.execute(query)

            result = cursor.fetchone()
            assert result is None or isinstance(result, expected_type)
            return result

    def clear_users(self) -> api.FilteredClear[dao_protos.User]:
        return FilteredClear(self._database, dao_models.Users, dao_models.Users.delete())

    async def delete_user(self, user_id: int, /) -> None:
        await self._execute(dao_models.Users.delete(dao_models.Users.c.id == user_id))

    async def get_user_by_id(
        self,
        user_id: typing.Union[int, str],
        /,
    ) -> typing.Optional[dao_protos.User]:
        return await self._fetch_one(dao_protos.User, dao_models.Users.select(dao_models.Users.c.id == user_id))

    async def get_user_by_username(
        self,
        username: typing.Union[int, str],
        /,
    ) -> typing.Optional[dao_protos.User]:
        return await self._fetch_one(dao_protos.User, dao_models.Users.select(dao_models.Users.c.username == username))

    def iter_users(self) -> api.DatabaseIterator[dao_protos.User]:
        return PostgreIterator(self._database, dao_models.Users, dao_models.Users.select())

    async def set_user(self, **kwargs: typing.Any) -> dao_protos.User:
        return await self._set(dao_protos.User, dao_models.Users.insert(kwargs).returning(dao_models.Users))

    async def update_user(self, user_id: int, /, **kwargs: typing.Any) -> typing.Optional[dao_protos.User]:
        if not kwargs:
            return await self.get_user_by_id(user_id)

        query = dao_models.Users.update(dao_models.Users.c.id == user_id).values(kwargs).returning(dao_models.Users)
        return await self._update(dao_protos.User, query)

    def clear_devices(self) -> api.FilteredClear[dao_protos.Device]:
        return FilteredClear(self._database, dao_models.Devices, dao_models.Devices.delete())

    async def delete_device(self, device_id: int, /) -> None:
        await self._execute(dao_models.Devices.delete(dao_models.Devices.c.id == device_id))

    async def get_device(self, device_id: int, /) -> typing.Optional[dao_protos.Device]:
        return await self._fetch_one(dao_protos.Device, dao_models.Devices.select(dao_models.Devices.c.id == device_id))

    def iter_devices(self) -> api.DatabaseIterator[dao_protos.Device]:
        return PostgreIterator(self._database, dao_models.Devices, dao_models.Devices.select())

    def iter_devices_for_user(self, user_id: int, /) -> api.DatabaseIterator[dao_protos.Device]:
        return PostgreIterator(
            self._database, dao_models.Devices, dao_models.Devices.select(dao_models.Devices.c.user_id == user_id)
        )

    async def set_device(self, **kwargs: typing.Any) -> dao_protos.Device:
        return await self._set(dao_protos.Device, dao_models.Devices.insert(kwargs).returning(dao_models.Devices))

    async def update_device(self, device_id: int, /, **kwargs: typing.Any) -> typing.Optional[dao_protos.Device]:
        if not kwargs:
            return await self.get_device(device_id)

        query = (
            dao_models.Devices.update(dao_models.Devices.c.id == device_id).values(kwargs).returning(dao_models.Devices)
        )
        return await self._update(dao_protos.Device, query)

    def clear_messages(self) -> api.FilteredClear[dao_protos.Message]:
        return FilteredClear(self._database, dao_models.Messages, dao_models.Messages.delete())

    async def delete_message(self, message_id: int, /) -> None:
        await self._execute(dao_models.Messages.delete(dao_models.Messages.c.id == message_id))

    async def get_message(
        self,
        message_id: int,
        /,
    ) -> typing.Optional[dao_protos.Message]:
        return await self._fetch_one(
            dao_protos.Message, dao_models.Messages.select(dao_models.Messages.c.id == message_id)
        )

    def iter_messages(self) -> api.DatabaseIterator[dao_protos.Message]:
        return PostgreIterator(self._database, dao_models.Messages, dao_models.Messages.select())

    def iter_messages_for_user(self, user_id: int, /) -> api.DatabaseIterator[dao_protos.Message]:
        return PostgreIterator(
            self._database, dao_models.Messages, dao_models.Messages.select(dao_models.Messages.c.user_id == user_id)
        )

    async def set_message(self, **kwargs: typing.Any) -> dao_protos.Message:
        return await self._set(dao_protos.Message, dao_models.Messages.insert(kwargs).returning(dao_models.Messages))

    async def update_message(self, message_id: int, /, **kwargs: typing.Any) -> typing.Optional[dao_protos.Message]:
        if not kwargs:
            return await self.get_message(message_id)

        query = (
            dao_models.Messages.update(dao_models.Messages.c.id == message_id)
            .values(kwargs)
            .returning(dao_models.Messages)
        )
        return await self._update(dao_protos.Message, query)

    def clear_files(self) -> api.FilteredClear[dao_protos.File]:
        return FilteredClear(self._database, dao_models.Files, dao_models.Files.delete())

    async def delete_file(self, file_id: int, /) -> None:
        await self._execute(dao_models.Files.delete(dao_models.Files.c.id == file_id))

    async def get_file(self, file_id: int, /) -> typing.Optional[dao_protos.File]:
        return await self._fetch_one(dao_protos.File, dao_models.Files.select(dao_models.Files.c.id == file_id))

    def iter_files(self) -> api.DatabaseIterator[dao_protos.File]:
        return PostgreIterator(self._database, dao_models.Files, dao_models.Files.select())

    def iter_files_for_message(self, message_id: int, /) -> api.DatabaseIterator[dao_protos.Message]:
        return PostgreIterator(
            self._database, dao_models.Files, dao_models.Files.select(dao_models.Files.c.message_id == message_id)
        )

    async def set_file(self, **kwargs: typing.Any) -> dao_protos.File:
        return await self._set(dao_protos.File, dao_models.Files.insert(kwargs).returning(dao_models.Files))

    async def update_file(self, file_id: int, /, **kwargs: typing.Any) -> typing.Optional[dao_protos.File]:
        if not kwargs:
            return await self.get_file(file_id)

        query = dao_models.Files.update(dao_models.Files.c.id == file_id).values(kwargs).returning(dao_models.Files)
        return await self._update(dao_protos.File, query)

    def clear_permissions(self) -> api.FilteredClear[dao_protos.Permission]:
        return FilteredClear(self._database, dao_models.Permissions, dao_models.Permissions.delete())

    async def delete_permission(self, message_id: int, user_id: int, /) -> None:
        await self._execute(
            dao_models.Permissions.delete(
                dao_models.Permissions.c.message_id == message_id and dao_models.Permissions.c.user_id == user_id
            )
        )

    async def get_permission(self, message_id: int, user_id: int, /) -> typing.Optional[dao_protos.Permission]:
        return await self._fetch_one(
            dao_protos.Permission,
            dao_models.Permissions.select(
                dao_models.Permissions.c.message_id == message_id and dao_models.Permissions.c.user_id == user_id
            ),
        )

    def iter_permissions(self) -> api.DatabaseIterator[dao_protos.Permission]:
        return PostgreIterator(self._database, dao_models.Permissions, dao_models.Permissions.select())

    def iter_permissions_for_message(self, message_id: int, /) -> api.DatabaseIterator[dao_protos.Permission]:
        query = dao_models.Permissions.select(dao_models.Permissions.c.message_id == message_id)
        return PostgreIterator(self._database, dao_models.Permissions, query)

    def iter_permissions_for_user(self, user_id: int, /) -> api.DatabaseIterator[dao_protos.Permission]:
        query = dao_models.Permissions.select(dao_models.Permissions.c.user_id == user_id)
        return PostgreIterator(self._database, dao_models.Permissions, query)

    async def set_permission(self, **kwargs: typing.Any) -> dao_protos.Permission:
        return await self._set(
            dao_protos.Permission, dao_models.Permissions.insert(kwargs).returning(dao_models.Permissions)
        )

    async def update_permission(
        self, message_id: int, user_id: int, /, **kwargs: typing.Any
    ) -> typing.Optional[dao_protos.Permission]:
        if not kwargs:
            return await self.get_permission(message_id, user_id)

        query = (
            dao_models.Permissions.update(
                dao_models.Permissions.c.message_id == message_id and dao_models.Permissions.c.user_id == user_id
            )
            .values(kwargs)
            .returning(dao_models.Permissions)
        )
        return await self._update(dao_protos.Permission, query)

    def clear_views(self) -> api.FilteredClear[dao_protos.View]:
        return FilteredClear(self._database, dao_models.Views, dao_models.Views.delete())

    async def delete_view(self, view_id: int, /) -> None:
        await self._execute(dao_models.Views.delete(dao_models.Views.c.id == view_id))

    async def get_view(self, view_id: int, /) -> typing.Optional[dao_protos.View]:
        return await self._fetch_one(dao_protos.View, dao_models.Views.select(dao_models.Views.c.id == view_id))

    def iter_views(self) -> api.DatabaseIterator[dao_protos.View]:
        return PostgreIterator(self._database, dao_models.Views, dao_models.Views.select())

    def iter_views_for_device(self, device_id: int) -> api.DatabaseIterator[dao_protos.View]:
        return PostgreIterator(
            self._database, dao_models.Views, dao_models.Views.select(dao_models.Views.c.device_id == device_id)
        )

    def iter_views_for_message(self, message_id: int, /) -> api.DatabaseIterator[dao_protos.View]:
        return PostgreIterator(
            self._database, dao_models.Views, dao_models.Views.select(dao_models.Views.c.message_id == message_id)
        )

    async def set_view(self, **kwargs: typing.Any) -> dao_protos.View:
        return await self._set(dao_protos.View, dao_models.Views.insert(kwargs).returning(dao_models.Views))


class DatabaseManager(typing.Generic[_DatabaseT]):
    __slots__: tuple[str, ...] = ("_database",)

    def __init__(self, url: str, /) -> None:
        self._database = PostgreDatabase.from_string(url)

    def __call__(self) -> PostgreDatabase:
        return self._database

    async def close(self) -> None:
        await self._database.close()
