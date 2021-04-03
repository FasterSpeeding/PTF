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

__all__: list[str] = ["RequireFlags", "UserAuth"]

import asyncio

import argon2
import fastapi.security

from . import flags
from . import refs
from .sql import api as sql_api
from .sql import dao_protos


class UserAuth:
    __slots__: tuple[str, ...] = ("hasher",)
    # This is a temporary hack around a missing case in how fastapi handles forward references
    __globals__ = {"fastapi": fastapi, "sql_api": sql_api, "refs": refs}  # TODO: open issue

    def __init__(self) -> None:
        # TODO: this seems bad, do we want to use a better algorithm?
        self.hasher: argon2.PasswordHasher = argon2.PasswordHasher(memory_cost=131072)

    async def __call__(
        self,
        credentials: fastapi.security.HTTPBasicCredentials = fastapi.Depends(fastapi.security.HTTPBasic()),
        database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    ) -> dao_protos.User:
        if user := await database.get_user_by_username(credentials.username):
            try:
                # TODO: does this even help?
                await asyncio.get_event_loop().run_in_executor(
                    None, self.hasher.verify, user.password_hash, credentials.password
                )

            except argon2.exceptions.VerifyMismatchError:
                pass

            else:
                return user

        raise fastapi.exceptions.HTTPException(
            401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Basic"}
        )

    async def hash_password(self, password: str, /) -> str:
        # TODO: does this even help?
        result = await asyncio.get_event_loop().run_in_executor(None, self.hasher.hash, password)
        assert isinstance(result, str)
        return result


class RequireFlags:
    __slots__: tuple[str, ...] = ("options",)
    # This is a temporary hack around a missing case in how fastapi handles forward references
    __globals__ = {"flags": flags, "dao_protos": dao_protos}  # TODO: open issue

    def __init__(self, flag_option: flags.UserFlags, /, *flags_options: flags.UserFlags) -> None:
        self.options = (flag_option, *flags_options)

    async def __call__(self, user: dao_protos.User = fastapi.Depends(refs.UserAuthProto)) -> dao_protos.User:
        # ADMIN access should allow all other permissions.
        if flags.UserFlags.ADMIN & user.flags or any((flags_ & user.flags) == flags_ for flags_ in self.options):
            return user

        raise fastapi.exceptions.HTTPException(403, detail="Missing permission(s) required to perform this action")
