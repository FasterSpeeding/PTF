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
use sqlx::Arguments;

use crate::{dao_models, sql};

#[derive(Clone)]
pub struct Pool {
    pool: sqlx::Pool<sqlx::Postgres>
}

impl Pool {
    pub fn new(pool: sqlx::Pool<sqlx::Postgres>) -> Self {
        Self { pool }
    }

    pub async fn connect(url: &str) -> Result<Self, sqlx::Error> {
        sqlx::PgPool::connect(url).await.map(Self::new)
    }
}


#[async_trait]
impl sql::Database for Pool {
    async fn delete_file(&self, message_id: &uuid::Uuid, file_name: &str) -> sql::DeleteResult {
        sqlx::query!(
            "DELETE FROM files WHERE message_id=$1 AND file_name=$2;",
            message_id,
            file_name
        )
        .execute(&self.pool)
        .await
        .map_err(Box::from)
        .map(|result| result.rows_affected() > 0)
    }

    async fn get_file(&self, message_id: &uuid::Uuid, file_name: &str) -> sql::DatabaseResult<dao_models::File> {
        sqlx::query_as!(
            dao_models::File,
            "SELECT * FROM files WHERE message_id=$1 AND file_name=$2;",
            message_id,
            file_name
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(Box::from)
    }

    async fn get_message(&self, message_id: &uuid::Uuid) -> sql::DatabaseResult<dao_models::Message> {
        sqlx::query_as!(dao_models::Message, "SELECT * FROM messages WHERE id=$1;", message_id)
            .fetch_optional(&self.pool)
            .await
            .map_err(Box::from)
    }

    async fn get_message_link(
        &self,
        message_id: &uuid::Uuid,
        link_token: &str
    ) -> sql::DatabaseResult<dao_models::MessageLink> {
        sqlx::query_as!(
            dao_models::MessageLink,
            "SELECT * FROM message_links WHERE message_id=$1 AND token=$2",
            message_id,
            link_token
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(Box::from)
    }

    async fn get_user_by_id(&self, user_id: &i64) -> sql::DatabaseResult<dao_models::User> {
        sqlx::query_as!(dao_models::User, "SELECT * FROM users WHERE id=$1;", user_id)
            .fetch_optional(&self.pool)
            .await
            .map_err(Box::from)
    }

    async fn get_user_by_username(&self, username: &str) -> sql::DatabaseResult<dao_models::User> {
        sqlx::query_as!(dao_models::User, "SELECT * FROM users WHERE username=$1;", username)
            .fetch_optional(&self.pool)
            .await
            .map_err(Box::from)
    }

    async fn set_user(&self, flags: &i64, password_hash: &str, username: &str) -> sql::SetResult<dao_models::User> {
        let result = sqlx::query_as!(
            dao_models::User,
            "INSERT INTO users (flags, password_hash, username) VALUES ($1, $2, $3) RETURNING *;",
            flags,
            password_hash,
            username
        )
        .fetch_one(&self.pool)
        .await;

        match result {
            Ok(user) => Ok(user),
            // TODO: this only works with postgres
            Err(sqlx::Error::Database(error)) if error.constraint().is_some() => Err(sql::SetError::Conflict),
            Err(other) => Err(sql::SetError::Unknown(Box::from(other)))
        }
    }

    // TODO: this doesn't feel rusty and how would setting fields to null work here?
    async fn update_user(
        &self,
        user_id: &i64,
        flags: &Option<i64>,
        password_hash: &Option<&str>,
        username: &Option<&str>
    ) -> sql::DatabaseResult<dao_models::User> {
        let mut query = String::new();
        let mut values = sqlx::postgres::PgArguments::default();
        values.add(user_id);
        let mut index: i8 = 1;

        query += "UPDATE USERS SET ";

        if let Some(flags) = flags {
            index += 1;
            query += &format!("flags = ${},", index);
            values.add(flags);
        };

        if let Some(value) = password_hash {
            index += 1;
            query += &format!("password_hash = ${}", index);
            values.add(value);
        };

        if let Some(username) = username {
            index += 1;
            query += &format!("username = ${},", index);
            values.add(username);
        };

        if query.ends_with(',') {
            query.pop();
        } else {
            // This covers the case when no fields are updated to avoid an SQL syntax error
            return self.get_user_by_id(user_id).await;
        }

        query += " WHERE id = $1 RETURNING *;";

        sqlx::query_as_with(&query, values)
            .fetch_optional(&self.pool)
            .await
            .map_err(Box::from)
    }
}
