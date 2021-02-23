use async_trait::async_trait;
use coi;
use crate::sql::dao_models;


pub type DatabaseResult<Model> = Result<Option<Model>, Box<dyn std::error::Error>>;


#[async_trait]
pub trait Database: coi::Inject {
    async fn get_file(&self, file_id: &i64) -> DatabaseResult<dao_models::File>;
    async fn get_message(&self, message_id: &i64) -> DatabaseResult<dao_models::Message>;
    async fn get_permission(&self, user_id: &i64, message_id: &i64) -> DatabaseResult<dao_models::Permission>;
    async fn get_user_by_id(&self, user_id: &i64) -> DatabaseResult<dao_models::User>;
    async fn get_user_by_username(&self, username: &String) -> DatabaseResult<dao_models::User>;
}
