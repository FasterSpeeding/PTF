-- -*- coding: utf-8 -*-
-- cython: language_level=3
-- BSD 3-Clause License
--
-- Copyright (c) 2021, Faster Speeding
-- All rights reserved.
--
-- Redistribution and use in source and binary forms, with or without
-- modification, are permitted provided that the following conditions are met:
--
-- * Redistributions of source code must retain the above copyright notice, this
--   list of conditions and the following disclaimer.
--
-- * Redistributions in binary form must reproduce the above copyright notice,
--   this list of conditions and the following disclaimer in the documentation
--   and/or other materials provided with the distribution.
--
-- * Neither the name of the copyright holder nor the names of its
--   contributors may be used to endorse or promote products derived from
--   this software without specific prior written permission.
--
-- THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
-- AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
-- IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
-- DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
-- FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
-- DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
-- SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
-- CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
-- OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
-- OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
CREATE TABLE IF NOT EXISTS users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    flags         BIGINT                   NOT NULL,
    username      VARCHAR                  NOT NULL UNIQUE, -- TODO: case insensitivity?
    password_hash VARCHAR                  NOT NULL,        -- argon2  -- TODO: bytea?

    CONSTRAINT user_pk
        PRIMARY KEY (id)
);


CREATE TABLE IF NOT EXISTS devices (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY,
    access             INT     NOT NULL,
    is_required_viewer BOOLEAN NOT NULL, -- TODO: This might be backwards
    name               VARCHAR NOT NULL,
    user_id            BIGINT  NOT NULL REFERENCES Users (id) ON DELETE CASCADE,

    CONSTRAINT device_pk
        PRIMARY KEY (id)
);


CREATE TABLE IF NOT EXISTS messages (
    id           BIGINT GENERATED ALWAYS AS IDENTITY,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expire_at    TIMESTAMP WITH TIME ZONE,
    is_public    BOOLEAN                  NOT NULL DEFAULT False,
    is_transient BOOLEAN                  NOT NULL, -- Find a better name for if this should delete after being viewed
    text         VARCHAR,
    title        VARCHAR,
    user_id     BIGINT                   NOT NULL REFERENCES Users (id) ON DELETE CASCADE,

    CONSTRAINT message_pk
        PRIMARY KEY (id)
);


-- These wil have to be manually deleted within the CDN and thus shouldn't cascade.
CREATE TABLE IF NOT EXISTS files (
    id         BIGINT GENERATED ALWAYS AS IDENTITY,
    file_name  VARCHAR NOT NULL,
    message_id BIGINT  NOT NULL REFERENCES Messages (id),

    CONSTRAINT file_pk
        PRIMARY KEY (id)
);


CREATE TABLE IF NOT EXISTS permissions (
    message_id  BIGINT NOT NULL REFERENCES Messages (id) ON DELETE CASCADE,
    permissions BIGINT NOT NULL,
    user_id     BIGINT NOT NULL REFERENCES Users (id) ON DELETE CASCADE,
    CONSTRAINT permission_pk
        PRIMARY KEY (message_id, user_id)
);


CREATE TABLE IF NOT EXISTS views (
    id         BIGINT GENERATED ALWAYS AS IDENTITY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    device_id  BIGINT                   NOT NULL REFERENCES Devices (id) ON DELETE CASCADE,
    message_id BIGINT                   NOT NULL REFERENCES Messages (id) ON DELETE CASCADE,

    CONSTRAINT view_pk
        PRIMARY KEY (id)
);
