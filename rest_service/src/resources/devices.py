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
    "get_user_devices",
    "patch_user_device",
    "post_user_devices",
]

import fastapi

from .. import dto_models
from .. import refs
from .. import utilities
from .. import validation
from ..sql import api as sql_api


@utilities.as_endpoint(
    "DELETE",
    "/devices",
    status_code=202,
    response_class=fastapi.Response,
    responses=dto_models.USER_AUTH_RESPONSE,
    tags=["Devices"],
)
async def delete_user_devices(
    device_names: set[str] = fastapi.Body(
        ..., min_length=validation.MINIMUM_NAME_LENGTH, max_length=validation.MAXIMUM_NAME_LENGTH
    ),
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> fastapi.Response:
    if device_names:
        database.clear_devices().filter("eq", ("user_id", auth.id)).filter("contains", ("name", device_names)).start()

    return fastapi.Response(status_code=202)


@utilities.as_endpoint(
    "GET",
    "/devices",
    response_model=list[dto_models.Device],
    responses=dto_models.USER_AUTH_RESPONSE,
    tags=["Devices"],
)
async def get_user_devices(
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> list[dto_models.Device]:
    return list(await database.iter_devices().filter("eq", ("user_id", auth.id)).map(dto_models.Device.from_orm))


@utilities.as_endpoint(
    "PATCH",
    "/devices/{device_name}",
    response_model=dto_models.Device,
    responses={
        **dto_models.USER_AUTH_RESPONSE,
        400: dto_models.BASIC_ERROR,
        404: dto_models.BASIC_ERROR,
    },
    tags=["Devices"],
)
async def patch_user_device(
    device_update: dto_models.ReceivedDeviceUpdate,
    device_name: str = fastapi.Path(
        ..., min_length=validation.MINIMUM_NAME_LENGTH, max_length=validation.MAXIMUM_NAME_LENGTH
    ),
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> dto_models.Device:
    try:
        new_device = await database.update_device_by_name(
            auth.id, device_name, **device_update.dict(exclude_unset=True)
        )

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc)) from None

    if not new_device:
        raise fastapi.exceptions.HTTPException(404, detail="Device not found.") from None

    return dto_models.Device.from_orm(new_device)


@utilities.as_endpoint(
    "POST",
    "/devices",
    response_model=dto_models.Device,
    responses={**dto_models.USER_AUTH_RESPONSE, 400: dto_models.BASIC_ERROR, 403: dto_models.BASIC_ERROR},
    tags=["Devices"],
)
async def post_user_devices(
    device: dto_models.Device,
    auth: dto_models.AuthUser = fastapi.Depends(refs.UserAuthProto),
    database: sql_api.DatabaseHandler = fastapi.Depends(refs.DatabaseProto),
) -> dto_models.Device:
    try:
        result = await database.set_device(
            is_required_viewer=device.is_required_viewer, user_id=auth.id, name=device.name
        )

    except sql_api.AlreadyExistsError:
        raise fastapi.exceptions.HTTPException(403, detail=f"Device `{device.name}` already exists.") from None

    except sql_api.DataError as exc:
        raise fastapi.exceptions.HTTPException(400, detail=str(exc)) from None

    return dto_models.Device.from_orm(result)
