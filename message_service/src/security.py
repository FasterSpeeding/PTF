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

__all__: list[str] = ["RequireFlags", "UserAuth"]

import base64
import ssl

import fastapi.security
import httpx

from . import dto_models
from . import flags
from . import refs
from .sql import dao_protos


def relay_handle_error(response: httpx.Response, /) -> fastapi.exceptions.HTTPException:
    try:
        data = response.json()
        message = data["errors"][0]["detail"]

    except Exception:
        message = "Internal server error" if response.status_code >= 500 else "Unknown error"

    authenticate = response.headers.get("WWW-Authenticate")
    headers = {"WWW-Authenticate": authenticate} if authenticate else None
    return fastapi.exceptions.HTTPException(response.status_code, detail=message, headers=headers)


class UserAuth:
    __slots__: tuple[str, ...] = ("base_url", "_client")

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        # By default AsyncClient will use it's own packaged CA bundle. We don't want this so we override it with a
        # default ssl context.
        self._client = httpx.AsyncClient(http2=True, verify=ssl.create_default_context())

    async def link_auth(self, link_token: str = fastapi.Query(...)) -> dto_models.LinkAuth:
        response = await self._client.get(f"{self.base_url}/links/{link_token}")

        if response.status_code == 200:
            found_link = dto_models.LinkAuth.parse_obj(response.json())
            return found_link

        if response.status_code == 404:
            raise fastapi.exceptions.HTTPException(403, detail="Unknown message link")

        raise relay_handle_error(response)

    async def user_auth(
        self,
        credentials: fastapi.security.HTTPBasicCredentials = fastapi.Depends(fastapi.security.HTTPBasic()),
    ) -> dto_models.AuthUser:
        auth = base64.b64encode(credentials.username.encode() + b":" + credentials.password.encode()).decode()
        response = await self._client.get(f"{self.base_url}/users/@me", headers={"Authorization": f"Basic {auth}"})

        if response.status_code == 200:
            user = dto_models.AuthUser.parse_obj(response.json())
            return user

        raise relay_handle_error(response)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()


class RequireFlags:
    __slots__: tuple[str, ...] = ("options",)
    # This is a temporary hack around a missing case in how fastapi handles forward references
    __globals__ = {"flags": flags, "dao_protos": dao_protos, "dto_models": dto_models, "refs": refs}  # TODO: open issue

    def __init__(self, flag_option: flags.UserFlags, /, *flags_options: flags.UserFlags) -> None:
        self.options = (flag_option, *flags_options)

    async def __call__(self, auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto)) -> dto_models.AuthUser:
        # ADMIN access should allow all other permissions.
        if flags.UserFlags.ADMIN & auth.flags or any((flags_ & auth.flags) == flags_ for flags_ in self.options):
            return auth

        raise fastapi.exceptions.HTTPException(403, detail="Missing permission(s) required to perform this action")
