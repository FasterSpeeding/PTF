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

__all__: list[str] = ["Users", "Devices", "Messages", "MessageLinks", "Files", "Views"]

import typing

import sqlalchemy
from sqlalchemy.dialects import postgresql

from .. import validation

ALWAYS: typing.Final[typing.Literal["ALWAYS"]] = "ALWAYS"
CASCADE: typing.Final[typing.Literal["CASCADE"]] = "CASCADE"

metadata = sqlalchemy.MetaData()

Users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BIGINT, sqlalchemy.Computed(ALWAYS)),
    sqlalchemy.Column(
        "created_at", sqlalchemy.TIMESTAMP(timezone=True), nullable=False, server_default=sqlalchemy.sql.func.now()
    ),
    sqlalchemy.Column("flags", sqlalchemy.BIGINT, nullable=False),
    sqlalchemy.Column("username", sqlalchemy.VARCHAR(validation.MAXIMUM_NAME_LENGTH), nullable=False),
    # Constraints
    sqlalchemy.PrimaryKeyConstraint("id", name="user_pk"),
    sqlalchemy.UniqueConstraint("username", name="user_username_uc"),
)


Devices = sqlalchemy.Table(
    "devices",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BIGINT, sqlalchemy.Computed(ALWAYS)),
    sqlalchemy.Column("access", sqlalchemy.INTEGER, nullable=False),
    sqlalchemy.Column("is_required_viewer", sqlalchemy.BOOLEAN, nullable=False),
    sqlalchemy.Column("name", sqlalchemy.VARCHAR(validation.MAXIMUM_NAME_LENGTH), nullable=False),
    sqlalchemy.Column("user_id", sqlalchemy.BIGINT, nullable=False),
    # Constraints
    sqlalchemy.PrimaryKeyConstraint("id", name="device_pk"),
    sqlalchemy.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete=CASCADE, name="device_user_id_fk"),
    sqlalchemy.UniqueConstraint("name", "user_id", name="device_uc"),
)

Messages = sqlalchemy.Table(
    "messages",
    metadata,
    sqlalchemy.Column("id", postgresql.UUID(as_uuid=True)),
    sqlalchemy.Column(
        "created_at", sqlalchemy.TIMESTAMP(timezone=True), nullable=False, server_default=sqlalchemy.sql.func.now()
    ),
    sqlalchemy.Column("expire_at", sqlalchemy.TIMESTAMP(timezone=True), nullable=True),
    sqlalchemy.Column("is_transient", sqlalchemy.BOOLEAN, nullable=False),
    sqlalchemy.Column("text", sqlalchemy.VARCHAR, nullable=True),
    sqlalchemy.Column("title", sqlalchemy.VARCHAR, nullable=True),
    sqlalchemy.Column("user_id", sqlalchemy.BIGINT, nullable=False),
    # Constraints
    sqlalchemy.PrimaryKeyConstraint("id", name="message_pk"),
    sqlalchemy.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete=CASCADE, name="message_user_id_fk"),
)


MessageLinks = sqlalchemy.Table(
    "message_links",
    metadata,
    sqlalchemy.Column("token", sqlalchemy.VARCHAR, nullable=False),
    sqlalchemy.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
    sqlalchemy.Column("expires_at", sqlalchemy.TIMESTAMP(timezone=True), nullable=False),
    # Constraints
    sqlalchemy.PrimaryKeyConstraint("message_id", "token", name="message_link_pk"),
    sqlalchemy.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete=CASCADE, name="message_link_fk"),
    sqlalchemy.UniqueConstraint("token", name="message_link_token_uc"),
)


Files = sqlalchemy.Table(
    "files",
    metadata,
    sqlalchemy.Column("content_type", sqlalchemy.VARCHAR, nullable=False),
    sqlalchemy.Column("file_name", sqlalchemy.VARCHAR, nullable=False),
    sqlalchemy.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
    # Constraints
    sqlalchemy.PrimaryKeyConstraint("file_name", "message_id", name="file_pk"),
    sqlalchemy.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete=CASCADE, name="files_message_id_fk"),
)


Views = sqlalchemy.Table(
    "views",
    metadata,
    sqlalchemy.Column(
        "created_at", sqlalchemy.TIMESTAMP(timezone=True), nullable=False, server_default=sqlalchemy.sql.func.now()
    ),
    sqlalchemy.Column("device_id", sqlalchemy.BIGINT, nullable=False),
    sqlalchemy.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
    # Constraints
    sqlalchemy.PrimaryKeyConstraint("device_id", "message_id", name="view_pk"),
    sqlalchemy.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete=CASCADE, name="views_device_id_fk"),
    sqlalchemy.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete=CASCADE, name="views_message_id_fk"),
)
