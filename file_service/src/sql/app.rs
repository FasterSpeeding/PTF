use rocket::fairing;
use sqlx;
use crate::sql::dao_models;
use crate::sql::traits;



pub struct Pool<DB: sqlx::Database>(sqlx::Pool<DB>);

// impl<DB: sqlx::Database> fairing::Fairing for Pool<DB> {
//     fn info(&self) -> fairing::Info {
//         fairing::Info {
//             name: "An asynchronous postgres database fairing",
//             kind: fairing::Kind::Request
//         }
//     }
// }

#[rocket::async_trait]
impl<'a, 'r> rocket::request::FromRequest<'a, 'r> for traits::Database {
    type Error = ();

    async fn from_request(request: &'a Request<'r>) -> Outcome<Box<dyn traits::Database>, ()> {
        return request.local_cache(Box<traits::Database>);
}



#[rocket::async_trait]
impl<DB: sqlx::Database> traits::Database for Pool<DB> {
// where 
//     sqlx::Pool<DB>: sqlx::Executor<'static> {
    async fn get_file(&self, file_id: &i64) -> traits::DatabaseResult<dao_models::File> {
        let result: Option<dao_models::File> = sqlx::query_as("SELECT * FROM files WHERE id=$1;")
            .bind(file_id)
            .fetch_optional(&self.0)
            .await?;
        return Ok(result);
    }

    async fn get_message(&self, message_id: &i64) -> traits::DatabaseResult<dao_models::Message> {
        let result: Option<dao_models::Message> = sqlx::query_as("SELECT * FROM messages WHERE id=$1;")
            .bind(message_id)
            .fetch_optional(&self.0)
            .await?;
        return Ok(result);
    }

    async fn get_permission(&self, user_id: &i64, message_id: &i64) -> traits::DatabaseResult<dao_models::Permission> {
        let result: Option<dao_models::Permission> = sqlx::query_as(
            "SELECT * FROM permissions WHERE user_id=$1 AND message_id=$2;"
        )
            .bind(user_id)
            .bind(message_id)
            .fetch_optional(&self.0)
            .await?;
        return Ok(result);
    }

    async fn get_user_by_id(&self, user_id: &i64) -> traits::DatabaseResult<dao_models::User> {
        let result: Option<dao_models::User> = sqlx::query_as("SELECT * FROM users WHERE id=$1;")
            .bind(user_id)
            .fetch_optional(&self.0)
            .await?;
        return Ok(result);
    }

    async fn get_user_by_username(&self, username: &String) -> traits::DatabaseResult<dao_models::User> {
        let result: Option<dao_models::User> = sqlx::query_as("SELECT * FROM users WHERE id=$1;")
            .bind(username)
            .fetch_optional(&self.0)
            .await?;
        return Ok(result);
    }
}

