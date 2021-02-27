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
    "delete_user_devices",
    "delete_my_user",
    "get_user_devices",
    "get_my_user",
    "patch_my_user",
    "patch_user_device",
    "post_user_devices",
    "put_user",
]

import typing

import fastapi

from .. import dto_models
from .. import flags
from .. import refs
from .. import security
from .. import utilities
from .. import validation
from ..sql import api as sql_api
from ..sql import dao_protos


@utilities.as_endpoint(
    "DELETE",
    "/users/@me",
    status_code=202,
    response_class=fastapi.Response,
    responses=dto_models.AUTH_RESPONSE,
    tags=["Users"],
)
async def delete_my_user(
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> fastapi.Response:
    await database.delete_user(user.id)
    return fastapi.Response(status_code=202)


@utilities.as_endpoint(
    "GET", "/users/@me", response_model=dto_models.User, responses=dto_models.AUTH_RESPONSE, tags=["Users"]
)
async def get_my_user(
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
) -> dto_models.User:
    return dto_models.User.from_orm(user)


@utilities.as_endpoint(
    "PATCH",
    "/users/@me",
    response_model=dto_models.User,
    responses={**dto_models.AUTH_RESPONSE, 400: dto_models.BASIC_ERROR},
    tags=["Users"],
)
async def patch_my_user(
    user_update: dto_models.ReceivedUserUpdate,
    stored_user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    hash_password: refs.HashPasswordProto = fastapi.Depends(refs.HashPasswordProto),
) -> dto_models.User:
    try:
        # TODO: validate flags being changed
        fields: dict[str, typing.Any] = user_update.dict(skip_defaults=True)
        if password := fields.pop("password"):
            fields["password_hash"] = hash_password(password)

        new_user = await database.update_user(stored_user.id, **fields)

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc))

    return dto_models.User.from_orm(new_user)


@utilities.as_endpoint(
    "PUT", "/users", response_model=dto_models.User, responses={400: dto_models.BASIC_ERROR}, tags=["Users"]
)
async def put_user(
    user: dto_models.ReceivedUser,
    _: typing.Any = fastapi.Depends(security.RequireFlags(flags.UserFlags.CREATE_USER)),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
    hash_password: refs.HashPasswordProto = fastapi.Depends(refs.HashPasswordProto),
) -> dto_models.User:
    if _ := await database.get_user_by_username(user.username):
        raise fastapi.exceptions.HTTPException(409, detail=f"User `{user.username}` already exists")

    try:
        password = hash_password(user.password)
        result = await database.set_user(flags=user.flags, username=user.username, password_hash=password)
        return dto_models.User.from_orm(result)

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc))


@utilities.as_endpoint(
    "DELETE",
    "/users/@me/devices",
    status_code=202,
    response_class=fastapi.Response,
    responses=dto_models.AUTH_RESPONSE,
    tags=["Devices"],
)
async def delete_user_devices(
    device_ids: set[int] = fastapi.Body(..., qe=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT),
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> fastapi.Response:
    database.clear_devices().filter("eq", ("user_id", user.id)).filter("contains", ("id", device_ids)).start()
    return fastapi.Response(status_code=202)


@utilities.as_endpoint(
    "GET",
    "/users/@me/devices",
    response_model=list[dto_models.Device],
    responses=dto_models.AUTH_RESPONSE,
    tags=["Devices"],
)
async def get_user_devices(
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> list[dto_models.Device]:
    return list(await database.iter_devices_for_user(user.id).map(dto_models.Device.from_orm))


async def retrieve_device(
    device_id: int = fastapi.Path(..., qe=validation.MINIMUM_BIG_INT, le=validation.MAXIMUM_BIG_INT),
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> dao_protos.Device:
    if stored_device := await database.get_device(device_id):
        if user.id == stored_device.user_id:
            return stored_device

        raise fastapi.exceptions.HTTPException(403, detail="You cannot access that device")

    raise fastapi.exceptions.HTTPException(404, detail="Device not found")


@utilities.as_endpoint(
    "PATCH",
    "/users/@me/devices/{device_id}",
    response_model=dto_models.Device,
    responses={
        **dto_models.AUTH_RESPONSE,
        400: dto_models.BASIC_ERROR,
        403: dto_models.BASIC_ERROR,
        404: dto_models.BASIC_ERROR,
    },
    tags=["Devices"],
)
async def patch_user_device(
    device_update: dto_models.ReceivedDeviceUpdate,
    stored_device: dao_protos.Device = fastapi.Depends(retrieve_device),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> dto_models.Device:
    try:
        new_device = await database.update_device(stored_device.id, **device_update.dict(skip_defaults=True))

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc))

    return dto_models.Device.from_orm(new_device)


@utilities.as_endpoint(
    "POST",
    "/users/@me/devices",
    response_model=dto_models.Device,
    responses={**dto_models.AUTH_RESPONSE, 400: dto_models.BASIC_ERROR},
    tags=["Devices"],
)
async def post_user_devices(
    device: dto_models.ReceivedDevice,
    user: dao_protos.User = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> dto_models.Device:
    try:
        result = await database.set_device(
            access=device.access, is_required_viewer=device.is_required_viewer, user_id=user.id, name=device.name
        )
        return dto_models.Device.from_orm(result)

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc))
