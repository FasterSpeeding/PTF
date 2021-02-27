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

__all__: list[str] = ["User", "Device", "Message", "File", "Permission", "View"]

import typing

if typing.TYPE_CHECKING:
    import datetime


@typing.runtime_checkable
class User(typing.Protocol):
    """Definition of the structure returned by database implementations for user entries."""

    __slots__: tuple[str, ...] = ()

    id: int
    created_at: datetime.datetime
    flags: int
    password_hash: str
    username: str


@typing.runtime_checkable
class Device(typing.Protocol):
    """Definition of the structure returned by database implementations for device entries."""

    __slots__: tuple[str, ...] = ()

    id: int
    access: int
    is_required_viewer: bool
    name: str
    user_id: int


@typing.runtime_checkable
class Message(typing.Protocol):
    """Definition of the structure returned by database implementations for message entries."""

    __slots__: tuple[str, ...] = ()

    id: int
    created_at: datetime.datetime
    expire_at: typing.Optional[datetime.datetime]
    is_public: bool
    is_transient: bool
    text: typing.Optional[str]
    title: typing.Optional[str]
    user_id: int


@typing.runtime_checkable
class File(typing.Protocol):
    """Definition of the structure returned by database implementations for file entries."""

    __slots__: tuple[str, ...] = ()

    file_name: str
    is_public: str
    message_id: int


@typing.runtime_checkable
class Permission(typing.Protocol):
    """Definition of the structure returned by database implementations for permission entries."""

    __slots__: tuple[str, ...] = ()

    message_id: int
    permissions: int
    user_id: int


@typing.runtime_checkable
class View(typing.Protocol):
    """Definition of the structure returned by database implementations for view entries."""

    __slots__: tuple[str, ...] = ()

    created_at: datetime.datetime
    device_id: int
    message_id: int
