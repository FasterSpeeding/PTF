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
"""Helper methods and consants used for validating received data."""
from __future__ import annotations

__all__: list[str] = ["MINIMUM_BIG_INT", "MINIMUM_TIMEDELTA", "MAXIMUM_BIG_INT", "validate_timedelta", "ZERO"]

import datetime
import typing

ZERO: typing.Final[int] = 0
"""Absolute zero."""
MINIMUM_BIG_INT: typing.Final[int] = -1 << 63
"""The inclusive minimum size a big int field can be."""
MAXIMUM_BIG_INT: typing.Final[int] = (1 << 63) - 1
"""The inclusive maximum size a big int field can be."""
MINIMUM_TIMEDELTA: typing.Final[datetime.timedelta] = datetime.timedelta(seconds=60)
_RAW_MINIMUM_TIMEDELTA: typing.Final[int] = round(MINIMUM_TIMEDELTA.total_seconds())
MAXIMUM_TIMEDELTA: typing.Final[datetime.timedelta] = datetime.timedelta(days=3650)  # 10 years
_RAW_MAXIMUM_TIMEDELTA: typing.Final[int] = round(MAXIMUM_TIMEDELTA.total_seconds())

USERNAME_REGEX: typing.Final[str] = r"^[\w\-\s]+$"
MINIMUM_NAME_LENGTH: typing.Final[int] = 3
MAXIMUM_NAME_LENGTH: typing.Final[int] = 32

MINIMUM_PASSWORD_LENGTH: typing.Final[int] = 8
MAXIMUM_PASSWORD_LENGTH: typing.Final[int] = 120


# TODO: document these limits
def validate_timedelta(delta: datetime.timedelta, /) -> datetime.timedelta:
    if delta < MINIMUM_TIMEDELTA:
        raise ValueError(f"time delta must be greater than or equal to {_RAW_MINIMUM_TIMEDELTA} seconds")

    elif delta > MAXIMUM_TIMEDELTA:
        raise ValueError(f"time delta must be less than or equal to {_RAW_MAXIMUM_TIMEDELTA} seconds")

    return delta
