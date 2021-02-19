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

__all__: list[str] = ["delete_messages", "get_message", "get_messages", "patch_message", "post_messages"]

import asyncio
import datetime
import typing

import fastapi

from .. import dto_models
from .. import flags
from .. import refs
from .. import utilities
from .. import validation
from ..sql import api as sql_api
from ..sql import dao_protos


async def retrieve_message(
    message_id: int = fastapi.Path(..., qe=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT),
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> dao_protos.Message:
    if stored_message := await database.get_message(message_id):
        if stored_message.user_id == user.id:
            return stored_message

        permission = await database.get_permission(message_id, user.id)

        if permission and permission.permissions != flags.PermissionFlags.NONE:
            return stored_message

        raise fastapi.exceptions.HTTPException(403, detail="You cannot access this message")

    raise fastapi.exceptions.HTTPException(404, detail="Message not found")


async def _delete_messages(message_ids: set[int], user_id: int, database: sql_api.DatabaseHandler) -> None:
    # TODO: handle permissions
    messages = database.iter_messages().filter("contains", ("id", message_ids)).filter("eq", ("user_id", user_id))
    message_ids = [message.id for message in await messages]
    await database.clear_files().filter("contains", ("message_id", message_ids))
    await database.clear_messages().filter("contains", ("id", message_ids))


@utilities.as_endpoint(
    "DELETE",
    "/users/@me/messages",
    status_code=202,
    response_class=fastapi.Response,
    responses=dto_models.AUTH_RESPONSE,
    tags=["Messages"],
)
async def delete_messages(
    message_ids: set[int] = fastapi.Body(..., qe=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT),
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> fastapi.Response:
    asyncio.create_task(_delete_messages(message_ids, user.id, database))
    return fastapi.Response(status_code=202)


@utilities.as_endpoint(
    "GET",
    "/users/@me/messages/{message_id}",
    response_model=dto_models.Message,
    responses={404: dto_models.BASIC_ERROR, 403: dto_models.BASIC_ERROR, **dto_models.AUTH_RESPONSE},
    tags=["Messages"],
)
async def get_message(
    message: dao_protos.Message = fastapi.Depends(retrieve_message),
) -> dto_models.Message:
    return dto_models.Message.from_orm(message)


@utilities.as_endpoint(
    "GET",
    "/users/@me/messages",
    response_model=list[dto_models.Message],
    responses={400: dto_models.BASIC_ERROR, **dto_models.AUTH_RESPONSE},
    tags=["Messages"],
)
async def get_messages(
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> list[dto_models.Message]:
    return [dto_models.Message.from_orm(message) for message in await database.iter_messages_for_user(user.id)]


@utilities.as_endpoint(
    "PATCH",
    "/users/@me/messages/{message_id}",
    response_model=dto_models.Message,
    responses={
        **dto_models.AUTH_RESPONSE,
        404: dto_models.BASIC_ERROR,
        403: dto_models.BASIC_ERROR,
        400: dto_models.BASIC_ERROR,
    },
    tags=["Messages"],
)
async def patch_message(
    message_update: dto_models.ReceivedMessageUpdate,
    stored_message: dao_protos.Message = fastapi.Depends(retrieve_message),
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> dto_models.Message:
    if stored_message.user_id != user.id:
        permission = await database.get_permission(stored_message.id, user.id)

        if not permission or permission.permissions != flags.PermissionFlags.READ_AND_WRITE:
            raise fastapi.exceptions.HTTPException(403, detail="You cannot edit this message")

    try:
        fields: dict[str, typing.Any] = message_update.dict(skip_defaults=True)
        if expire_after := fields.pop("expire_after", None):
            assert isinstance(expire_after, datetime.timedelta)
            fields["expire_at"] = datetime.datetime.now(tz=datetime.timezone.utc) + expire_after

        new_message = await database.update_message(stored_message.id, **fields)

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc))

    return dto_models.Message.from_orm(new_message)


@utilities.as_endpoint(
    "POST",
    "/users/@me/messages",
    response_model=dto_models.Message,
    responses={**dto_models.AUTH_RESPONSE, 400: dto_models.BASIC_ERROR},
    tags=["Messages"],
)
async def post_messages(
    message: dto_models.ReceivedMessage,
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> dto_models.Message:
    # TODO: files
    try:
        expire_at: typing.Optional[datetime.datetime] = None
        if message.expire_after:
            expire_at = datetime.datetime.now(tz=datetime.timezone.utc) + message.expire_after

        result = await database.set_message(
            expire_at=expire_at,
            is_public=message.is_public,
            is_transient=message.is_transient,
            text=message.text,
            title=message.title,
            user_id=user.id,
        )

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc))

    return dto_models.Message.from_orm(result)
