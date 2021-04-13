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
    id              UUID                        NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE    NOT NULL    DEFAULT CURRENT_TIMESTAMP,
    flags           BIGINT                      NOT NULL,
    password_hash   VARCHAR                     NOT NULL,                       -- argon2  -- TODO: binary?
    username        VARCHAR(32)                 NOT NULL,                       -- TODO: case insensitivity?

    CONSTRAINT user_pk
        PRIMARY KEY (id),

    CONSTRAINT user_username_uc
        UNIQUE (username)
);


-- TODO: replace id as primary key with (name, user_id)
CREATE TABLE IF NOT EXISTS devices (
    id                  BIGINT      NOT NULL    GENERATED ALWAYS AS IDENTITY,   -- TODO: replace with (name, user_id)
    is_required_viewer  BOOLEAN     NOT NULL,                                   -- TODO: This might be backwards
    name                VARCHAR(32) NOT NULL,
    user_id             UUID        NOT NULL,

    CONSTRAINT device_pk
        PRIMARY KEY (id),

    CONSTRAINT device_user_id_fk
        FOREIGN KEY (user_id)
        REFERENCES users (id)
        ON DELETE CASCADE,

    CONSTRAINT device_uc
        UNIQUE (name, user_id)
);


 -- TODO: Find a better name for if this should delete after being viewed than "is_transient"
CREATE TABLE IF NOT EXISTS messages (
    id              UUID                        NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE    NOT NULL                        DEFAULT CURRENT_TIMESTAMP,
    expire_at       TIMESTAMP WITH TIME ZONE,
    is_transient    BOOLEAN                     NOT NULL,
    text            VARCHAR,                    -- TODO: not nullable?
    title           VARCHAR,                    -- TODO: not nullable?
    user_id         UUID                        NOT NULL,

    CONSTRAINT message_pk
        PRIMARY KEY (id),

    CONSTRAINT message_user_id_fk
        FOREIGN KEY (user_id)
        REFERENCES users (id)
        ON DELETE CASCADE
);


-- TODO: is_unlisted?
CREATE TABLE IF NOT EXISTS message_links (
    access      SMALLINT                    NOT NULL,
    expires_at  TIMESTAMP WITH TIME ZONE,
    message_id  UUID                        NOT NULL,
    resource    VARCHAR,
    token       CHAR(32)                    NOT NULL,

    CONSTRAINT message_link_pk
        PRIMARY KEY (token),

    CONSTRAINT message_link_fk
        FOREIGN KEY (message_id)
        REFERENCES messages (id)
        ON DELETE CASCADE
);


-- The actual files for deleted files will be deleted by a cron-job running on the file service at one point.
CREATE TABLE IF NOT EXISTS files (
    content_type    VARCHAR                     NOT NULL,  -- TODO: length limit
    file_name       VARCHAR(120)                NOT NULL,  -- TODO: length limit
    message_id      UUID                        NOT NULL,  -- TODO: hash
    set_at          TIMESTAMP WITH TIME ZONE    NOT NULL,

    CONSTRAINT file_pk
        PRIMARY KEY (set_at, message_id),

    CONSTRAINT file_uc
        UNIQUE (file_name, message_id),

    CONSTRAINT files_message_id_fk
        FOREIGN KEY (message_id)
        REFERENCES messages (id)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS views (  -- TODO: remove?
    created_at  TIMESTAMP WITH TIME ZONE    NOT NULL    DEFAULT CURRENT_TIMESTAMP,
    device_id   BIGINT                      NOT NULL,
    message_id  UUID                        NOT NULL,

    CONSTRAINT view_pk
        PRIMARY KEY (device_id, message_id),

    CONSTRAINT views_device_id_fk
        FOREIGN KEY (device_id)
        REFERENCES devices (id)
        ON DELETE CASCADE,

    CONSTRAINT views_message_id_fk
        FOREIGN KEY (message_id)
        REFERENCES messages (id)
        ON DELETE CASCADE
);
