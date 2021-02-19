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

__all__: list[str] = ["Users", "Devices", "Messages", "Files", "Permissions", "Views"]

import typing

import sqlalchemy

CASCADE: typing.Final[typing.Literal["CASCADE"]] = "CASCADE"

metadata = sqlalchemy.MetaData()

Users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BIGINT, primary_key=True),
    sqlalchemy.Column("created_at", sqlalchemy.TIMESTAMP(timezone=True), nullable=False),
    sqlalchemy.Column("flags", sqlalchemy.BIGINT, nullable=False),
    sqlalchemy.Column("password_hash", sqlalchemy.VARCHAR, nullable=False),
    sqlalchemy.Column("username", sqlalchemy.VARCHAR, nullable=False, unique=True),
)

Devices = sqlalchemy.Table(
    "devices",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BIGINT, primary_key=True),
    sqlalchemy.Column("access", sqlalchemy.INTEGER, nullable=False),
    sqlalchemy.Column("is_required_viewer", sqlalchemy.BOOLEAN, nullable=False),
    sqlalchemy.Column("name", sqlalchemy.VARCHAR, nullable=False),
    sqlalchemy.Column(
        "user_id", sqlalchemy.BIGINT, sqlalchemy.ForeignKey("users.id", ondelete=CASCADE), nullable=False
    ),
)

Messages = sqlalchemy.Table(
    "messages",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BIGINT, primary_key=True),
    sqlalchemy.Column("created_at", sqlalchemy.TIMESTAMP(timezone=True), nullable=False),
    sqlalchemy.Column("expire_at", sqlalchemy.TIMESTAMP(timezone=True), nullable=True),
    sqlalchemy.Column("is_public", sqlalchemy.BOOLEAN, nullable=False),
    sqlalchemy.Column("is_transient", sqlalchemy.BOOLEAN, nullable=False),
    sqlalchemy.Column("text", sqlalchemy.VARCHAR, nullable=True),
    sqlalchemy.Column("title", sqlalchemy.VARCHAR, nullable=True),
    sqlalchemy.Column(
        "user_id", sqlalchemy.BIGINT, sqlalchemy.ForeignKey("users.id", ondelete=CASCADE), nullable=False
    ),
)


Files = sqlalchemy.Table(
    "files",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BIGINT, primary_key=True),
    sqlalchemy.Column("file_name", sqlalchemy.VARCHAR, nullable=False),
    sqlalchemy.Column("message_id", sqlalchemy.BIGINT, sqlalchemy.ForeignKey("messages.id"), nullable=False),
)


Permissions = sqlalchemy.Table(
    "permissions",
    metadata,
    sqlalchemy.Column(
        "message_id", sqlalchemy.BIGINT, sqlalchemy.ForeignKey("message.id", ondelete=CASCADE), primary_key=True
    ),
    sqlalchemy.Column("permissions", sqlalchemy.BIGINT, nullable=False),
    sqlalchemy.Column(
        "user_id", sqlalchemy.BIGINT, sqlalchemy.ForeignKey("users.id", ondelete=CASCADE), primary_key=True
    ),
)


Views = sqlalchemy.Table(
    "views",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BIGINT, primary_key=True),
    sqlalchemy.Column("created_at", sqlalchemy.TIMESTAMP(timezone=True), nullable=False),
    sqlalchemy.Column(
        "device_id", sqlalchemy.BIGINT, sqlalchemy.ForeignKey("devices.id", ondelete=CASCADE), nullable=False
    ),
    sqlalchemy.Column(
        "message_id", sqlalchemy.BIGINT, sqlalchemy.ForeignKey("messages.id", ondelete=CASCADE), nullable=False
    ),
)
