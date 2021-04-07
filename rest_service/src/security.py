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

__all__: list[str] = ["RequireFlags", "UserAuth", "InitiatedAuth"]

import base64
import typing

import aiohttp
import fastapi.security

from . import dto_models
from . import flags
from . import refs
from .sql import api as sql_api
from .sql import dao_protos


class UserAuth:
    __slots__: tuple[str, ...] = ("base_url", "_client")
    # This is a temporary hack around a missing case in how fastapi handles forward references
    __globals__ = {"fastapi": fastapi, "sql_api": sql_api, "refs": refs}  # TODO: open issue

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self._client: typing.Optional[aiohttp.ClientSession] = None

    def _acquire_client(self) -> aiohttp.ClientSession:
        self._client = aiohttp.ClientSession()
        return self._client

    async def __call__(  # TODO: less repeated boilerplate
        self,
        credentials: fastapi.security.HTTPBasicCredentials = fastapi.Depends(fastapi.security.HTTPBasic()),
        database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    ) -> InitiatedAuth:
        client = self._client

        if client is None:
            client = self._acquire_client()

        auth = base64.b64encode(credentials.username.encode() + b":" + credentials.password.encode()).decode()
        response = await client.get(self.base_url + "/users/@me", headers={"Authorization": f"Basic {auth}"})

        if response.status == 200:
            user = dto_models.AuthUser.parse_obj(await response.json())
            return InitiatedAuth(self, user, credentials)

        try:
            data = await response.json()
            message = data["errors"][0]["detail"]

        except Exception:
            message = "Internal server error" if response.status >= 500 else "Unknown error"

        headers = {"WWW-Authenticate": "Basic"} if response.status == 401 else None
        raise fastapi.exceptions.HTTPException(response.status, detail=message, headers=headers)

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    async def create_user(
        self, credentials: fastapi.security.HTTPBasicCredentials, username: str, user: dto_models.ReceivedUser
    ) -> dto_models.AuthUser:
        client = self._client

        if client is None:
            client = self._acquire_client()

        auth = base64.b64encode(credentials.username.encode() + b":" + credentials.password.encode()).decode()
        response = await client.put(
            self.base_url + f"/users/{username}",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
            data=user.json(),
        )

        if response.status == 200:
            return dto_models.AuthUser.parse_obj(await response.json())

        try:
            data = await response.json()
            message = data["errors"][0]["detail"]

        except Exception:
            message = "Internal server error" if response.status >= 500 else "Unknown error"

        headers = {"WWW-Authenticate": "Basic"} if response.status == 401 else None
        raise fastapi.exceptions.HTTPException(response.status, detail=message, headers=headers)

    async def update_user(
        self, credentials: fastapi.security.HTTPBasicCredentials, user: dto_models.ReceivedUserUpdate
    ) -> typing.Optional[dto_models.AuthUser]:
        client = self._client

        if client is None:
            client = self._acquire_client()

        auth = base64.b64encode(credentials.username.encode() + b":" + credentials.password.encode()).decode()
        data = user.dict(exclude_unset=True)

        if not data:
            return None

        response = await client.patch(
            self.base_url + "/users/@me", headers={"Authorization": f"Basic {auth}"}, json=data
        )

        if response.status == 200:
            return dto_models.AuthUser.parse_obj(await response.json())

        try:
            data = await response.json()
            message = data["errors"][0]["detail"]

        except Exception:
            message = "Internal server error" if response.status >= 500 else "Unknown error"

        headers = {"WWW-Authenticate": "Basic"} if response.status == 401 else None
        raise fastapi.exceptions.HTTPException(response.status, detail=message, headers=headers)


class InitiatedAuth:
    __slots__: typing.Sequence[str] = ("_auth_handler", "_credentials", "_user")

    def __init__(
        self, auth_handler: UserAuth, user: dto_models.AuthUser, credentials: fastapi.security.HTTPBasicCredentials
    ) -> None:
        self._auth_handler = auth_handler
        self._credentials = credentials
        self._user = user

    @property
    def user(self) -> dto_models.AuthUser:
        return self._user

    async def create_user(self, username: str, user: dto_models.ReceivedUser) -> dto_models.AuthUser:
        return await self._auth_handler.create_user(self._credentials, username, user)

    async def update_user(self, user: dto_models.ReceivedUserUpdate) -> dto_models.AuthUser:
        return (await self._auth_handler.update_user(self._credentials, user)) or self._user


class RequireFlags:
    __slots__: tuple[str, ...] = ("options",)
    # This is a temporary hack around a missing case in how fastapi handles forward references
    __globals__ = {"flags": flags, "dao_protos": dao_protos, "refs": refs}  # TODO: open issue

    def __init__(self, flag_option: flags.UserFlags, /, *flags_options: flags.UserFlags) -> None:
        self.options = (flag_option, *flags_options)

    async def __call__(self, auth: refs.UserAuthProto = fastapi.Depends(refs.AuthGetterProto)) -> refs.UserAuthProto:
        # ADMIN access should allow all other permissions.
        user = auth.user
        if flags.UserFlags.ADMIN & user.flags or any((flags_ & user.flags) == flags_ for flags_ in self.options):
            return auth

        raise fastapi.exceptions.HTTPException(403, detail="Missing permission(s) required to perform this action")
