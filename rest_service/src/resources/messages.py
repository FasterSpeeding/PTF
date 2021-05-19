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
    "delete_messages",
    "delete_message_views",
    "get_shared_message",
    "get_message",
    "get_messages",
    "get_message_views",
    "patch_message",
    "post_message",
    "put_message_view",
]

import asyncio
import datetime
import typing
import uuid

import fastapi

from .. import dto_models
from .. import refs
from .. import utilities
from .. import validation
from ..sql import api as sql_api
from ..sql import dao_protos


async def user_auth_message(
    message_id: uuid.UUID = fastapi.Path(...),
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> dao_protos.Message:
    if stored_message := await database.get_message(message_id, auth.id):
        return stored_message

    raise fastapi.exceptions.HTTPException(404, detail="Message not found.") from None


@utilities.as_endpoint(
    "DELETE",
    "/messages",
    status_code=202,
    response_class=fastapi.Response,
    responses=dto_models.USER_AUTH_RESPONSE,
    tags=["Messages"],
)
async def delete_messages(
    message_ids: set[uuid.UUID] = fastapi.Body(...),
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> fastapi.Response:
    if message_ids:
        database.clear_messages().filter("contains", ("id", message_ids)).filter("eq", ("user_id", auth.id)).start()

    return fastapi.Response(status_code=202)


async def _delete_views(
    auth: dto_models.AuthUser,
    device_names: set[str],
    message: dao_protos.Message,
    database: sql_api.DatabaseHandler,
) -> None:
    devices = (
        await database.iter_devices()
        .filter("eq", ("user_id", auth.id))
        .filter("contains", ("name", device_names))
        .map(lambda d: d.id)
    )
    await database.clear_views().filter("eq", ("message_id", message.id)).filter(
        "contains", ("device_id", devices)
    ).execute()


@utilities.as_endpoint(
    "DELETE",
    "/messages/{message_id}/views",
    response_class=fastapi.Response,
    status_code=204,
    responses={**dto_models.USER_AUTH_RESPONSE, 404: dto_models.BASIC_ERROR},
    tags=["Message Views"],
)
async def delete_message_views(
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    device_names: set[str] = fastapi.Body(
        ..., min_length=validation.MINIMUM_NAME_LENGTH, max_length=validation.MAXIMUM_NAME_LENGTH
    ),
    message: dao_protos.Message = fastapi.Depends(user_auth_message),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> fastapi.Response:
    if device_names:
        asyncio.create_task(_delete_views(auth, device_names, message, database))

    return fastapi.Response(status_code=204)


@utilities.as_endpoint(
    "GET",
    "/messages/{message_id}/views",
    response_model=list[dto_models.View],
    status_code=200,
    responses={**dto_models.USER_AUTH_RESPONSE, 404: dto_models.BASIC_ERROR},
    tags=["Message Views"],
)
async def get_message_views(
    message: dao_protos.Message = fastapi.Depends(user_auth_message),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> list[dto_models.View]:
    # Avoid unnecessary extra-lookups if there's no views
    if not (view_daos := list(await database.iter_views().filter("eq", ("message_id", message.id)))):
        return []

    device_ids = [view.device_id for view in view_daos]
    devices_iter = await database.iter_devices().filter("contains", ("id", device_ids))
    devices = {d.id: d.name for d in devices_iter}

    views = []
    for dao in view_daos:
        dto = dto_models.View.from_orm(dao)
        dto.device_name = devices[dao.device_id]
        views.append(dto)

    return views


@utilities.as_endpoint(
    "PUT",
    "/messages/{message_id}/views/{device_name}",
    response_model=dto_models.View,
    status_code=201,
    responses={
        # This behaviour of 204 vs 201 is specified under https://datatracker.ietf.org/doc/html/rfc7231#section-4.3.4
        204: {"description": "The view already exists."},
        400: dto_models.BASIC_ERROR,
        404: dto_models.BASIC_ERROR,
        **dto_models.USER_AUTH_RESPONSE,
    },
    tags=["Message Views"],
)
async def put_message_view(
    device_name: str = fastapi.Path(
        ..., min_length=validation.MINIMUM_NAME_LENGTH, max_length=validation.MAXIMUM_NAME_LENGTH
    ),
    message: dao_protos.Message = fastapi.Depends(user_auth_message),
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> typing.Union[dto_models.View, fastapi.Response]:
    if not (device := await database.get_device_by_name(auth.id, device_name)):
        raise fastapi.exceptions.HTTPException(404, detail="Device not found.") from None

    try:
        view = await database.set_view(device_id=device.id, message_id=message.id)

    except sql_api.AlreadyExistsError:
        return fastapi.Response(status_code=204)

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc)) from None

    result = dto_models.View.from_orm(view)
    result.device_name = device_name
    return result


@utilities.as_endpoint(
    "GET",
    "/messages/{message_id}/shared",
    response_model=dto_models.Message,
    responses=dto_models.LINK_AUTH_RESPONSE,
    tags=["Shared Messages"],
)
async def get_shared_message(
    _: dto_models.LinkAuth = fastapi.Depends(refs.LinkAuthProto),
    message_id: uuid.UUID = fastapi.Path(...),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    metadata: utilities.Metadata = fastapi.Depends(utilities.Metadata),
) -> dto_models.Message:
    if message := await database.get_message(message_id):
        return await get_message(message, database, metadata)

    # In the rare case that a message is deleted as we're getting our response from the auth service we want to 404 here
    raise fastapi.exceptions.HTTPException(404, detail="Message not found.")


@utilities.as_endpoint(
    "GET",
    "/messages/{message_id}",
    response_model=dto_models.Message,
    responses={404: dto_models.BASIC_ERROR, **dto_models.USER_AUTH_RESPONSE},
    tags=["Messages"],
)
async def get_message(
    message: dao_protos.Message = fastapi.Depends(user_auth_message),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    metadata: utilities.Metadata = fastapi.Depends(utilities.Metadata),
) -> dto_models.Message:
    result = dto_models.Message.from_orm(message)
    files = await database.iter_files().filter("eq", ("message_id", message.id)).map(dto_models.File.from_orm)
    result.files.extend(files)
    result.with_paths(metadata)
    return result


@utilities.as_endpoint(
    "GET",
    "/messages",
    response_model=list[dto_models.Message],
    responses={400: dto_models.BASIC_ERROR, **dto_models.USER_AUTH_RESPONSE},
    tags=["Messages"],
)
async def get_messages(
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    metadata: utilities.Metadata = fastapi.Depends(utilities.Metadata),
) -> list[dto_models.Message]:
    files_iter = await database.iter_messages().filter("eq", ("user_id", auth.id)).map(dto_models.Message.from_orm)
    messages = {message.id: message for message in files_iter}
    files = (
        await database.iter_files()
        .filter("contains", ("message_id", set(messages.keys())))
        .map(dto_models.File.from_orm)
    )

    for file in files:
        file.with_paths(metadata)
        messages[file.message_id].files.append(file)

    for message in messages.values():
        message.with_paths(metadata, recursive=False)

    return list(messages.values())


@utilities.as_endpoint(
    "PATCH",
    "/messages/{message_id}",
    response_model=dto_models.Message,
    responses={
        **dto_models.USER_AUTH_RESPONSE,
        404: dto_models.BASIC_ERROR,
        400: dto_models.BASIC_ERROR,
    },
    tags=["Messages"],
)
async def patch_message(
    message_update: dto_models.ReceivedMessageUpdate,
    message_id: uuid.UUID = fastapi.Path(...),
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    metadata: utilities.Metadata = fastapi.Depends(utilities.Metadata),
) -> dto_models.Message:
    fields: dict[str, typing.Any] = message_update.dict(exclude_unset=True)
    if (expire_after := fields.pop("expire_after", ...)) is not ...:
        assert expire_after is None or isinstance(expire_after, datetime.timedelta)
        if expire_after:
            fields["expire_at"] = datetime.datetime.now(tz=datetime.timezone.utc) + expire_after

        else:
            fields["expire_at"] = None

    try:
        new_message = await database.update_message(message_id, auth.id, **fields)

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc)) from None

    if not new_message:
        raise fastapi.exceptions.HTTPException(404, detail="Message not found") from None

    result = dto_models.Message.from_orm(new_message)
    files = await database.iter_files().filter("eq", ("message_id", result.id)).map(dto_models.File.from_orm)
    result.files.extend(files)
    result.with_paths(metadata)
    return result


@utilities.as_endpoint(
    "POST",
    "/messages",
    response_model=dto_models.Message,
    status_code=201,
    responses={**dto_models.USER_AUTH_RESPONSE, 400: dto_models.BASIC_ERROR},
    tags=["Messages"],
)
async def post_message(
    message: dto_models.ReceivedMessage,
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    metadata: utilities.Metadata = fastapi.Depends(utilities.Metadata),
) -> dto_models.Message:
    expire_at: typing.Optional[datetime.datetime] = None
    if message.expire_after:
        expire_at = datetime.datetime.now(tz=datetime.timezone.utc) + message.expire_after

    try:
        result = await database.set_message(
            expire_at=expire_at,
            is_transient=message.is_transient,
            text=message.text,
            title=message.title,
            user_id=auth.id,
        )

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc)) from None

    response = dto_models.Message.from_orm(result)
    response.with_paths(metadata, recursive=False)
    return response
