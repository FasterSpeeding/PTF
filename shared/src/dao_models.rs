// BSD 3-Clause License
//
// Copyright (c) 2021, Lucina
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// * Redistributions of source code must retain the above copyright notice, this
//   list of conditions and the following disclaimer.
//
// * Redistributions in binary form must reproduce the above copyright notice,
//   this list of conditions and the following disclaimer in the documentation
//   and/or other materials provided with the distribution.
//
// * Neither the name of the copyright holder nor the names of its contributors
//   may be used to endorse or promote products derived from this software
//   without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.
#[derive(Debug, sqlx::FromRow)]
pub struct User {
    pub id:            uuid::Uuid,
    pub created_at:    chrono::DateTime<chrono::Utc>,
    pub flags:         i64, // TODO: flags?
    pub password_hash: String,
    pub username:      String
}


#[derive(Debug, sqlx::FromRow)]
pub struct Device {
    pub id:                 i64,
    pub is_required_viewer: bool,
    pub name:               String,
    pub user_id:            uuid::Uuid
}

#[derive(Debug, sqlx::FromRow)]
pub struct Message {
    pub id:           uuid::Uuid,
    pub created_at:   chrono::DateTime<chrono::Utc>,
    pub expires_at:   Option<chrono::DateTime<chrono::Utc>>,
    pub is_transient: bool,
    pub text:         Option<String>,
    pub title:        Option<String>,
    pub user_id:      uuid::Uuid
}

#[derive(Debug, sqlx::FromRow)]
pub struct File {
    pub content_type: String,
    pub file_name:    String,
    pub message_id:   uuid::Uuid,
    pub set_at:       chrono::DateTime<chrono::Utc>
}

#[derive(Debug, sqlx::FromRow)]
pub struct View {
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub device_id:  i64,
    pub message_id: uuid::Uuid
}

#[derive(Debug, sqlx::FromRow)]
pub struct MessageLink {
    pub access:     i16,
    pub expires_at: Option<chrono::DateTime<chrono::Utc>>,
    pub message_id: uuid::Uuid,
    pub resource:   Option<String>,
    pub token:      String
}
