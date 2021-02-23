use async_trait::async_trait;
use coi::Inject;
use sqlx;
use std::sync::Arc;
use crate::sql::dao_models;
use crate::sql::traits;



#[derive(Clone)]
#[derive(Inject)]
#[coi(provides dyn traits::Database with Pool::new(pool))]
// pub struct Pool<DB: sqlx::Database> {
pub struct Pool {
    #[coi(inject)]
    pool: Arc<sqlx::Pool<sqlx::Postgres>>
}


// impl<DB: sqlx::Database> Pool<DB> {
//     pub fn new(pool: Arc<sqlx::Pool<DB>>) -> Pool<DB> {
//         return Pool { pool: pool };
//     }
// }
impl Pool {
    pub fn new(pool: Arc<sqlx::Pool<sqlx::Postgres>>) -> Pool {
        return Pool { pool: pool };
    }
}


#[async_trait]
// impl<DB: sqlx::Database> traits::Database for Pool<DB> {
impl traits::Database for Pool {
// where 
//     sqlx::Pool<DB>: sqlx::Executor<'static> {
    async fn get_file(&self, file_id: &i64) -> traits::DatabaseResult<dao_models::File> {
        let result = sqlx::query_as!(dao_models::File, "SELECT * FROM files WHERE id=$1;", file_id)
            .fetch_optional(self.pool.as_ref())
            .await?;
        return Ok(result);
    }

    async fn get_message(&self, message_id: &i64) -> traits::DatabaseResult<dao_models::Message> {
        let result = sqlx::query_as!(dao_models::Message, "SELECT * FROM messages WHERE id=$1;", message_id)
            .fetch_optional(self.pool.as_ref())
            .await?;
        return Ok(result);
    }

    async fn get_permission(&self, user_id: &i64, message_id: &i64) -> traits::DatabaseResult<dao_models::Permission> {
        let result = sqlx::query_as!(
            dao_models::Permission,
            "SELECT * FROM permissions WHERE user_id=$1 AND message_id=$2;",
            user_id,
            message_id
        )
            .fetch_optional(self.pool.as_ref())
            .await?;
        return Ok(result);
    }

    async fn get_user_by_id(&self, user_id: &i64) -> traits::DatabaseResult<dao_models::User> {
        let result = sqlx::query_as!(dao_models::User, "SELECT * FROM users WHERE id=$1;", user_id)
            .fetch_optional(self.pool.as_ref())
            .await?;
        return Ok(result);
    }

    async fn get_user_by_username(&self, username: &String) -> traits::DatabaseResult<dao_models::User> {
        let result = sqlx::query_as!(dao_models::User, "SELECT * FROM users WHERE username=$1;", username)
            .fetch_optional(self.pool.as_ref())
            .await?;
        return Ok(result);
    }
}




