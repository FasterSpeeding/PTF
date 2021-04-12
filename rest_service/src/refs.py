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

__all__: list[str] = ["AuthGetterProto", "DatabaseProto", "UserAuthProto"]

import typing

if typing.TYPE_CHECKING:
    from . import dto_models
    from .sql import api as sql_api


class DatabaseProto(typing.Protocol):
    def __call__(self) -> sql_api.DatabaseHandler:
        raise NotImplementedError


class UserAuthProto:
    @property
    def user(self) -> dto_models.AuthUser:
        raise NotImplementedError


class AuthGetterProto(typing.Protocol):
    def __call__(self) -> UserAuthProto:
        raise NotImplementedError


def __new(_: type[typing.Any]) -> None:
    raise NotImplementedError


# `__new__` is explicitly provided with no arguments here to avoid an issue with the OAI spec doc gen where it detects
# parameters from protocol dependencies. See https://github.com/tiangolo/fastapi/issues/2144
# This isn't declared on the protocols themselves as to avoid it becoming a part of the interface.
# As a note this does have the side effect of preventing us from inheriting from these protocols for the impls.


for _name, _value in vars().copy().items():
    if _name.endswith("Proto"):
        _value.__new__ = __new

del _name, _value
