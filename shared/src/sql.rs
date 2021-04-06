// BSD 3-Clause License
//
// Copyright (c) 2021, Faster Speeding
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
use std::error::Error;
use std::fmt;

use async_trait::async_trait;

use crate::dao_models;

pub type DeleteResult = Result<bool, Box<dyn Error>>;
pub type DatabaseResult<Model> = Result<Option<Model>, Box<dyn Error>>; // TODO: merge
pub type SetResult<Model> = Result<Model, SetError>; // TODO: merge


#[derive(Debug)]
pub enum SetError {
    Conflict,
    Unknown(Box<dyn Error>)
}


impl SetError {
    pub fn conflict() -> Self {
        Self::Conflict
    }

    pub fn unknown(error: Box<dyn Error>) -> Self {
        Self::Unknown(error)
    }
}


impl Error for SetError {
}


impl fmt::Display for SetError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Conflict => write!(f, "Entry already exists"),
            Self::Unknown(error) => error.fmt(f)
        }
    }
}


#[async_trait]
pub trait Database: Sync {
    async fn delete_file(&self, message_id: &uuid::Uuid, file_name: &str) -> DeleteResult;
    async fn get_file(&self, message_id: &uuid::Uuid, file_name: &str) -> DatabaseResult<dao_models::File>;
    async fn get_message(&self, message_id: &uuid::Uuid) -> DatabaseResult<dao_models::Message>;
    async fn get_message_link(
        // TODO: gonna need mutating and deleting methods
        &self,
        message_id: &uuid::Uuid,
        link_token: &str
    ) -> DatabaseResult<dao_models::MessageLink>;
    async fn get_user_by_id(&self, user_id: &i64) -> DatabaseResult<dao_models::User>;
    async fn get_user_by_username(&self, username: &str) -> DatabaseResult<dao_models::User>;
    async fn set_user(&self, flags: &i64, password_hash: &str, username: &str) -> SetResult<dao_models::User>;
    // TODO: this is bad
    async fn update_user(
        &self,
        user_id: &i64,
        flags: &Option<i64>,
        password_hash: &Option<&str>,
        username: &Option<&str>
    ) -> DatabaseResult<dao_models::User>;
}
