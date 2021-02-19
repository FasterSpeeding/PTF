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

__all__: list[str] = ["build"]

import os
import typing

import dotenv
import fastapi

from . import refs
from .sql import api as sql_api


async def _on_shutdown(database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto)) -> None:
    await database.close()


def build(sql_builder: typing.Optional[typing.Callable[[], sql_api.DatabaseHandler]] = None, /) -> fastapi.FastAPI:
    from . import resources
    from . import security
    from . import utilities
    from .sql import impl as sql_impl

    dotenv.load_dotenv()
    database_url = os.getenv("database_url")
    if database_url is None:
        raise RuntimeError("Must set database connection URL in .env")

    if not sql_builder:
        sql_builder = sql_impl.DatabaseManager(database_url)

    user_auth_handler = security.UserAuth()

    server = fastapi.FastAPI(title="PTF API")
    server.dependency_overrides[refs.DatabaseProto] = sql_builder
    server.dependency_overrides[refs.UserAuthProto] = user_auth_handler
    server.dependency_overrides[refs.HashPasswordProto] = lambda: user_auth_handler.hash_password
    server.add_event_handler("shutdown", _on_shutdown)

    for value in vars(resources).values():
        if isinstance(value, utilities.EndpointDescriptor):
            server.add_api_route(**value.build())

    return server
