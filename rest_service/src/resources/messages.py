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

import datetime
import typing

import fastapi

from .. import dto_models
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
        if stored_message.user_id != user.id:
            raise fastapi.exceptions.HTTPException(403, detail="You cannot access this message.") from None

        return stored_message

    raise fastapi.exceptions.HTTPException(404, detail="Message not found.") from None


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
    database.clear_messages().filter("contains", ("id", message_ids)).filter("eq", ("user_id", user.id)).start()
    return fastapi.Response(status_code=202)


async def viewer_device(
    device_name: typing.Optional[str] = fastapi.Header(
        default=None, min_length=validation.MINIMUM_NAME_LENGTH, max_length=validation.MAXIMUM_NAME_LENGTH
    ),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
) -> typing.Optional[dao_protos.Device]:
    if device_name is None:
        return None

    if device := await database.get_device_by_name(user.id, device_name):
        return device

    raise fastapi.exceptions.HTTPException(404, detail="Device not found.") from None


@utilities.as_endpoint(
    "GET",
    "/users/@me/messages/{message_id}",
    response_model=dto_models.Message,
    responses={404: dto_models.BASIC_ERROR, **dto_models.AUTH_RESPONSE},
    tags=["Messages"],
)
async def get_message(
    message: dao_protos.Message = fastapi.Depends(retrieve_message),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    viewer: typing.Optional[dao_protos.Device] = fastapi.Depends(viewer_device),
) -> dto_models.Message:
    if viewer and viewer.user_id == message.user_id:
        try:
            await database.set_view(message_id=message.id, device_id=viewer.id)

        except sql_api.AlreadyExistsError:
            pass

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
    return list(
        await database.iter_messages_for_user(user.id).order_by("id", ascending=False).map(dto_models.Message.from_orm)
    )


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
        raise fastapi.exceptions.HTTPException(403, detail="You cannot edit this message.") from None

    try:
        fields: dict[str, typing.Any] = message_update.dict(skip_defaults=True)
        if (expire_after := fields.pop("expire_after", ...)) is not ...:
            assert expire_after is None or isinstance(expire_after, datetime.timedelta)
            if expire_after:
                fields["expire_at"] = datetime.datetime.now(tz=datetime.timezone.utc) + expire_after

            else:
                fields["expire_at"] = None

        new_message = await database.update_message(stored_message.id, **fields)
        assert new_message is not None, "existence should've been verified by retrieve_message"

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc)) from None

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
        raise fastapi.exceptions.HTTPException(400, detail=str(exc)) from None

    return dto_models.Message.from_orm(result)
