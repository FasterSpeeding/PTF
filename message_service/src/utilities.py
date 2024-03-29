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

__all__: list[str] = ["as_endpoint", "EndpointDescriptor", "Metadata", "MethodT"]

import os
import typing
import urllib.parse
import uuid

import dotenv
from fastapi import datastructures
from fastapi import responses as responses_
from fastapi import types as fastapi_types

if typing.TYPE_CHECKING:
    import collections.abc as collections

    import fastapi
    from fastapi import encoders
    from fastapi import params
    from fastapi import routing
    from starlette import routing as starlette_routing


MethodT = typing.Literal[
    "CONNECT",
    "DELETE",
    "GET",
    "HEAD",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
    "TRACE",
]


class EndpointDescriptor(typing.Generic[fastapi_types.DecoratedCallable]):
    __slots__: tuple[str, ...] = ("_endpoint", "_kwargs")

    def __init__(
        self,
        *,
        endpoint: fastapi_types.DecoratedCallable,
        methods: typing.Union[MethodT, set[MethodT]],
        **kwargs: typing.Any,
    ) -> None:
        self._endpoint = endpoint
        kwargs["endpoint"] = endpoint
        kwargs["methods"] = {methods} if isinstance(methods, str) else set(methods)
        self._kwargs = kwargs

    if typing.TYPE_CHECKING:
        __call__: fastapi_types.DecoratedCallable

    else:

        def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            return self._endpoint(*args, **kwargs)

    def build(self) -> dict[str, typing.Any]:
        return self._kwargs.copy()


if typing.TYPE_CHECKING:

    def as_endpoint(
        methods: typing.Union[MethodT, collections.Iterable[MethodT]],
        path: str,
        /,
        *,
        response_model: typing.Optional[type[typing.Any]] = None,
        status_code: int = 200,
        tags: typing.Optional[list[str]] = None,
        dependencies: typing.Optional[collections.Sequence[params.Depends]] = None,
        summary: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        response_description: str = "Successful Response",
        responses: typing.Optional[dict[typing.Union[int, str], dict[str, typing.Any]]] = None,
        deprecated: typing.Optional[bool] = None,
        operation_id: typing.Optional[str] = None,
        response_model_include: typing.Optional[typing.Union[encoders.SetIntStr, encoders.DictIntStrAny]] = None,
        response_model_exclude: typing.Optional[typing.Union[encoders.SetIntStr, encoders.DictIntStrAny]] = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        response_class: typing.Union[
            type[fastapi.Response], datastructures.DefaultPlaceholder
        ] = datastructures.Default(responses_.JSONResponse),
        name: typing.Optional[str] = None,
        route_class_override: typing.Optional[type[routing.APIRoute]] = None,
        callbacks: typing.Optional[list[starlette_routing.BaseRoute]] = None,
    ) -> collections.Callable[[fastapi_types.DecoratedCallable], EndpointDescriptor[fastapi_types.DecoratedCallable]]:
        raise NotImplementedError


else:

    def as_endpoint(
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> collections.Callable[[fastapi_types.DecoratedCallable], EndpointDescriptor[fastapi_types.DecoratedCallable]]:
        def decorator(
            endpoint: fastapi_types.DecoratedCallable, /
        ) -> EndpointDescriptor[fastapi_types.DecoratedCallable]:
            assert len(args) == 2, f"Too many positional arguments passed, expected 2 but got {len(args)}"
            return EndpointDescriptor(**kwargs, methods=args[0], path=args[1], endpoint=endpoint)

        return decorator


REQUIRED_ENV_ENTRIES: typing.Final[list[str]] = [
    "auth_service_address",
    "database_url",
    "file_service_hostname",
    "message_service_address",
    "message_service_hostname",
    "message_service_cert",
    "message_service_key",
]


class Metadata:
    __slots__: tuple[str, ...] = (
        "address",
        "auth_service_address",
        "database_url",
        "file_service_hostname",
        "hostname",
        "log_level",
        "port",
        "ssl_cert",
        "ssl_key",
    )

    def __init__(self) -> None:
        dotenv.load_dotenv()

        values = {key: os.getenv(key) for key in REQUIRED_ENV_ENTRIES}

        for key, value in values.items():
            if value is None:
                raise RuntimeError(f"{key} must be set in .env or environment")

        values = typing.cast("typing.Mapping[str, str]", values)

        address = urllib.parse.urlparse(values["message_service_address"])
        self.address = address.hostname
        self.hostname = values["message_service_hostname"]
        self.port = address.port or "8080"

        self.auth_service_address = values["auth_service_address"]
        # TODO: there must be a better way to handle the database url between rust and python
        self.database_url = "//" + values["database_url"].split("//", 1)[1]
        self.file_service_hostname = values["file_service_hostname"]
        self.log_level = (os.getenv("log_level") or "info").lower()
        self.ssl_cert = values["message_service_cert"]
        self.ssl_key = values["message_service_key"]

    def file_private_uri(self, message_id: uuid.UUID, file_name: str, /) -> str:
        return self.file_service_hostname + f"/messages/{message_id}/files/{urllib.parse.quote(file_name)}"

    def file_public_uri(self, file_name: str, /) -> str:
        return self.file_service_hostname + f"/links/{{link_token}}/files/{urllib.parse.quote(file_name)}"

    def message_private_uri(self, message_id: uuid.UUID, /) -> str:
        return self.hostname + f"/messages/{message_id}"

    def message_public_uri(self) -> str:
        return self.hostname + "/links/{link_token}/message"

    def __call__(self) -> Metadata:
        return self
