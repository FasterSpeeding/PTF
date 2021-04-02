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
use async_trait::async_trait;

use crate::sql::{dao_models, traits};

#[derive(Clone)]
pub struct Pool {
    pool: sqlx::Pool<sqlx::Postgres>
}


impl Pool {
    pub fn new(pool: sqlx::Pool<sqlx::Postgres>) -> Self {
        Self { pool }
    }
}


#[async_trait]
impl traits::Database for Pool {
    async fn get_file(&self, message_id: &i64, file_name: &str) -> traits::DatabaseResult<dao_models::File> {
        let result = sqlx::query_as!(
            dao_models::File,
            "SELECT * FROM files WHERE message_id=$1 AND file_name=$2;",
            message_id,
            file_name
        )
        .fetch_optional(&self.pool)
        .await?;
        Ok(result)
    }

    async fn get_message(&self, message_id: &i64) -> traits::DatabaseResult<dao_models::Message> {
        let result = sqlx::query_as!(dao_models::Message, "SELECT * FROM messages WHERE id=$1;", message_id)
            .fetch_optional(&self.pool)
            .await?;
        Ok(result)
    }

    async fn get_user_by_id(&self, user_id: &i64) -> traits::DatabaseResult<dao_models::User> {
        let result = sqlx::query_as!(dao_models::User, "SELECT * FROM users WHERE id=$1;", user_id)
            .fetch_optional(&self.pool)
            .await?;
        Ok(result)
    }

    async fn get_user_by_username(&self, username: &str) -> traits::DatabaseResult<dao_models::User> {
        let result = sqlx::query_as!(dao_models::User, "SELECT * FROM users WHERE username=$1;", username)
            .fetch_optional(&self.pool)
            .await?;
        Ok(result)
    }
}
