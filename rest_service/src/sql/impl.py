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
import collections.abc as collections
import operator
import typing
import urllib.parse
import uuid

# https://github.com/MagicStack/asyncpg/issues/699
import asyncpg.exceptions  # TODO: wait for asyncpg to add python 3.10 support
import sqlalchemy.exc
import sqlalchemy.ext.asyncio

from . import api
from . import dao_models
from . import dao_protos

if typing.TYPE_CHECKING:
    import types

_DatabaseT = typing.TypeVar("_DatabaseT", bound=api.DatabaseHandler)
_PostgresCollectionT = typing.TypeVar("_PostgresCollectionT", bound="_PostgresCollection[typing.Any]")
_ValueT = typing.TypeVar("_ValueT")
_OtherValueT = typing.TypeVar("_OtherValueT")
_QueryT = typing.Union[sqlalchemy.sql.Select, sqlalchemy.sql.Delete, sqlalchemy.sql.Insert, sqlalchemy.sql.Update]


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
            root_error = exc_val.__cause__.__cause__
            if isinstance(root_error, asyncpg.exceptions.IntegrityConstraintViolationError):
                if isinstance(root_error, asyncpg.exceptions.UniqueViolationError):
                    raise api.AlreadyExistsError(str(root_error.args[0])) from None

                raise api.DataError(str(root_error.args[0])) from None

        elif isinstance(exc_val, sqlalchemy.exc.DBAPIError):
            root_error = exc_val.__cause__.__cause__
            if isinstance(root_error, asyncpg.exceptions.DataError):
                raise api.DataError(str(root_error.args[0])) from None


# Type error


_operators: dict[api.FilterTypeT, collections.Callable[..., typing.Any]] = {
    "lt": operator.lt,
    "le": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
    "ge": operator.ge,
    "gt": operator.gt,
}


class _PostgresCollection(typing.Generic[_ValueT]):
    __slots__: tuple[str, ...] = ("_engine", "_query", "_table")

    def __init__(
        self, engine: sqlalchemy.ext.asyncio.AsyncEngine, table: sqlalchemy.Table, query: sqlalchemy.sql.Select, /
    ) -> None:
        self._engine = engine
        self._query = query
        self._table = table

    async def collect(self) -> collections.Collection[_ValueT]:
        async with self._engine.begin() as connection:
            cursor = await connection.execute(self._query)
            result = cursor.fetchall()
            assert isinstance(result, collections.Collection)
            return result

    async def count(self) -> int:
        async with self._engine.begin() as connection:
            cursor = await connection.execute(self._query)
            assert isinstance(cursor.rowcount, int)
            return cursor.rowcount

    def filter(
        self: _PostgresCollectionT, filter_type: api.FilterTypeT, *rules: tuple[str, typing.Any]
    ) -> _PostgresCollectionT:
        namespace = self._table.entity_namespace
        if filter_type == "contains":
            self._query = self._query.filter(*(namespace[attr].in_(value) for attr, value in rules))

        else:
            operator_ = _operators[filter_type]
            self._query = self._query.filter(*(operator_(namespace[attr], value) for attr, value in rules))

        return self

    def filter_truth(self: _PostgresCollectionT, *fields: str, truth: bool = True) -> _PostgresCollectionT:
        operator_ = operator.truth if truth else operator.not_
        namespace = self._table.entity_namespace
        self._query = self._query.filter(*(operator_(namespace[attr]) for attr in fields))
        return self

    # TODO: can we make this lazier?
    async def iter(self) -> collections.Iterator[_ValueT]:
        return iter(await self.collect())

    def limit(self: _PostgresCollectionT, limit: int, /) -> _PostgresCollectionT:
        self._query = self._query.limit(limit)
        return self

    async def map(self, cast: typing.Callable[[_ValueT], _OtherValueT], /) -> collections.Iterator[_OtherValueT]:
        return map(cast, await self.collect())

    def order_by(self: _PostgresCollectionT, field: str, /, ascending: bool = True) -> _PostgresCollectionT:
        order = sqlalchemy.asc if ascending else sqlalchemy.desc
        self._query = self._query.order_by(order(self._table.entity_namespace[field]))
        return self


class PostgreIterator(_PostgresCollection[_ValueT], api.DatabaseIterator[_ValueT]):
    __slots__: tuple[str, ...] = ()

    def __await__(self) -> collections.Generator[typing.Any, None, collections.Iterator[_ValueT]]:
        return self.iter().__await__()


class FilteredClear(_PostgresCollection[_ValueT], api.FilteredClear[_ValueT]):
    __slots__: tuple[str, ...] = ()

    def __await__(self) -> collections.Generator[typing.Any, None, int]:
        return self.execute().__await__()

    async def execute(self) -> int:
        return await self.count()

    def start(self) -> asyncio.Task[int]:
        return asyncio.create_task(self.execute())


class PostgreDatabase(api.DatabaseHandler):
    __slots__: tuple[str, ...] = ("_database",)

    def __init__(self, url: urllib.parse.SplitResult, /) -> None:
        engine_url = sqlalchemy.engine.URL.create(
            drivername=url.scheme,
            username=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port or 5432,
            database=url.path.strip("/") or "ptf",
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
            assert isinstance(results[0], expected_type)

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
        await self._execute(dao_models.Users.delete(dao_models.Users.c["id"] == user_id))

    async def get_user_by_id(self, user_id: typing.Union[int, str], /) -> typing.Optional[dao_protos.User]:
        return await self._fetch_one(dao_protos.User, dao_models.Users.select(dao_models.Users.c["id"] == user_id))

    async def get_user_by_username(self, username: typing.Union[int, str], /) -> typing.Optional[dao_protos.User]:
        return await self._fetch_one(
            dao_protos.User, dao_models.Users.select(dao_models.Users.c["username"] == username)
        )

    def iter_users(self) -> api.DatabaseIterator[dao_protos.User]:
        return PostgreIterator(self._database, dao_models.Users, dao_models.Users.select())

    def clear_devices(self) -> api.FilteredClear[dao_protos.Device]:
        return FilteredClear(self._database, dao_models.Devices, dao_models.Devices.delete())

    async def delete_device_by_id(self, device_id: int, /) -> None:
        await self._execute(dao_models.Devices.delete(dao_models.Devices.columns["id"] == device_id))

    async def delete_device_by_name(self, user_id: int, device_name: str, /) -> None:
        columns = dao_models.Devices.columns
        query = dao_models.Devices.delete(
            sqlalchemy.and_(columns["user_id"] == user_id, columns["name"] == device_name)
        )
        await self._execute(query)

    async def get_device_by_id(self, device_id: int, /) -> typing.Optional[dao_protos.Device]:
        return await self._fetch_one(
            dao_protos.Device, dao_models.Devices.select(dao_models.Devices.columns["id"] == device_id)
        )

    async def get_device_by_name(self, user_id: int, device_name: str, /) -> typing.Optional[dao_protos.Device]:
        columns = dao_models.Devices.columns
        query = dao_models.Devices.select(
            sqlalchemy.and_(columns["user_id"] == user_id, columns["name"] == device_name)
        )
        return await self._fetch_one(dao_protos.Device, query)

    def iter_devices(self) -> api.DatabaseIterator[dao_protos.Device]:
        return PostgreIterator(self._database, dao_models.Devices, dao_models.Devices.select())

    def iter_devices_for_user(self, user_id: int, /) -> api.DatabaseIterator[dao_protos.Device]:
        return PostgreIterator(
            self._database, dao_models.Devices, dao_models.Devices.select(dao_models.Devices.c["user_id"] == user_id)
        )

    async def set_device(self, **kwargs: typing.Any) -> dao_protos.Device:
        return await self._set(dao_protos.Device, dao_models.Devices.insert(kwargs).returning(dao_models.Devices))

    async def update_device_by_id(self, device_id: int, /, **kwargs: typing.Any) -> typing.Optional[dao_protos.Device]:
        if not kwargs:
            return await self.get_device_by_id(device_id)

        query = (
            dao_models.Devices.update(dao_models.Devices.columns["id"] == device_id)
            .values(kwargs)
            .returning(dao_models.Devices)
        )
        return await self._update(dao_protos.Device, query)

    async def update_device_by_name(
        self, user_id: int, device_name: str, /, **kwargs: typing.Any
    ) -> typing.Optional[dao_protos.Device]:
        if not kwargs:
            return await self.get_device_by_name(user_id, device_name)

        columns = dao_models.Devices.columns
        query = (
            dao_models.Devices.update(sqlalchemy.and_(columns["user_id"] == user_id, columns["name"] == device_name))
            .values(kwargs)
            .returning(dao_models.Devices)
        )
        return await self._update(dao_protos.Device, query)

    def clear_messages(self) -> api.FilteredClear[dao_protos.Message]:
        return FilteredClear(self._database, dao_models.Messages, dao_models.Messages.delete())

    async def delete_message(self, message_id: uuid.UUID, /) -> None:
        await self._execute(dao_models.Messages.delete(dao_models.Messages.c["id"] == message_id))

    async def get_message(self, message_id: uuid.UUID, /) -> typing.Optional[dao_protos.Message]:
        return await self._fetch_one(
            dao_protos.Message, dao_models.Messages.select(dao_models.Messages.c["id"] == message_id)
        )

    def iter_messages(self) -> api.DatabaseIterator[dao_protos.Message]:
        return PostgreIterator(self._database, dao_models.Messages, dao_models.Messages.select())

    def iter_messages_for_user(self, user_id: int, /) -> api.DatabaseIterator[dao_protos.Message]:
        return PostgreIterator(
            self._database, dao_models.Messages, dao_models.Messages.select(dao_models.Messages.c["user_id"] == user_id)
        )

    async def set_message(self, **kwargs: typing.Any) -> dao_protos.Message:
        kwargs["id"] = uuid.uuid4()
        return await self._set(dao_protos.Message, dao_models.Messages.insert(kwargs).returning(dao_models.Messages))

    async def update_message(
        self, message_id: uuid.UUID, /, **kwargs: typing.Any
    ) -> typing.Optional[dao_protos.Message]:
        if not kwargs:
            return await self.get_message(message_id)

        query = (
            dao_models.Messages.update(dao_models.Messages.c["id"] == message_id)
            .values(kwargs)
            .returning(dao_models.Messages)
        )
        return await self._update(dao_protos.Message, query)

    async def get_file(self, message_id: uuid.UUID, file_name: str, /) -> typing.Optional[dao_protos.File]:
        columns = dao_models.Files.columns
        query = dao_models.Files.select(
            sqlalchemy.and_(columns["message_id"] == message_id, columns["name"] == file_name)
        )
        return await self._fetch_one(dao_protos.File, query)

    def iter_files(self) -> api.DatabaseIterator[dao_protos.File]:
        return PostgreIterator(self._database, dao_models.Files, dao_models.Files.select())

    def iter_files_for_message(self, message_id: uuid.UUID, /) -> api.DatabaseIterator[dao_protos.Message]:
        return PostgreIterator(
            self._database, dao_models.Files, dao_models.Files.select(dao_models.Files.c["message_id"] == message_id)
        )

    def clear_message_links(self) -> api.FilteredClear[dao_protos.MessageLink]:
        return FilteredClear(self._database, dao_models.MessageLinks, dao_models.MessageLinks.delete())

    async def delete_message_link(self, message_id: uuid.UUID, token: str, /) -> None:
        columns = dao_models.MessageLinks.columns
        query = dao_models.MessageLinks.delete(
            sqlalchemy.and_(columns["message_id"] == message_id, columns["token"] == token)
        )
        await self._execute(query)

    async def get_message_link(self, message_id: uuid.UUID, token: str, /) -> typing.Optional[dao_protos.MessageLink]:
        columns = dao_models.MessageLinks.columns
        query = dao_models.MessageLinks.select(
            sqlalchemy.and_(columns["message_id"] == message_id, columns["token"] == token)
        )
        return await self._fetch_one(dao_protos.MessageLink, query)

    def iter_message_links(self) -> api.DatabaseIterator[dao_protos.MessageLink]:
        return PostgreIterator(self._database, dao_models.MessageLinks, dao_models.MessageLinks.select())

    def iter_message_link_for_message(self, message_id: uuid.UUID, /) -> api.DatabaseIterator[dao_protos.MessageLink]:
        return PostgreIterator(
            self._database,
            dao_models.MessageLinks,
            dao_models.MessageLinks.select(dao_models.MessageLinks.c["message_id"] == message_id),
        )

    async def set_message_link(self, **kwargs: typing.Any) -> dao_protos.MessageLink:
        return await self._set(
            dao_protos.MessageLink, dao_models.MessageLinks.insert(kwargs).returning(dao_models.MessageLinks)
        )

    def clear_views(self) -> api.FilteredClear[dao_protos.View]:
        return FilteredClear(self._database, dao_models.Views, dao_models.Views.delete())

    async def delete_view(self, device_id: int, message_id: uuid.UUID, /) -> None:
        columns = dao_models.Views.columns
        query = dao_models.Views.delete(
            sqlalchemy.and_(columns["device_id"] == device_id, columns["message_id"] == message_id)
        )
        await self._execute(query)

    async def get_view(self, device_id: int, message_id: uuid.UUID, /) -> typing.Optional[dao_protos.View]:
        columns = dao_models.Views.columns
        query = dao_models.Views.select(
            sqlalchemy.and_(columns["device_id"] == device_id, columns["message_id"] == message_id)
        )
        return await self._fetch_one(dao_protos.View, query)

    def iter_views(self) -> api.DatabaseIterator[dao_protos.View]:
        return PostgreIterator(self._database, dao_models.Views, dao_models.Views.select())

    def iter_views_for_device(self, device_id: int, /) -> api.DatabaseIterator[dao_protos.View]:
        return PostgreIterator(
            self._database, dao_models.Views, dao_models.Views.select(dao_models.Views.c["device_id"] == device_id)
        )

    def iter_views_for_message(self, message_id: uuid.UUID, /) -> api.DatabaseIterator[dao_protos.View]:
        return PostgreIterator(
            self._database, dao_models.Views, dao_models.Views.select(dao_models.Views.c["message_id"] == message_id)
        )

    async def set_view(self, **kwargs: typing.Any) -> dao_protos.View:
        return await self._set(dao_protos.View, dao_models.Views.insert(kwargs).returning(dao_models.Views))


class DatabaseManager:
    __slots__: tuple[str, ...] = ("_database",)

    def __init__(self, url: str, /) -> None:
        self._database = PostgreDatabase.from_string(url)

    def __call__(self) -> PostgreDatabase:
        return self._database

    async def close(self) -> None:
        await self._database.close()
