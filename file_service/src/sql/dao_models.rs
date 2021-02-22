// use chrono;
// use serde;
use sqlx::types::chrono;


// #[derive(Clone, Debug, serde::Deserialize)]
#[derive(sqlx::FromRow)]
pub struct User {
    pub id: i64,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub flags: i64,  // TODO: flags?
    pub username: String,
    pub password_hash: String
}


// #[derive(Clone, Debug, serde::Deserialize)]
#[derive(sqlx::FromRow)]
pub struct Device {
    pub id: i64,
    pub access: i16, // What is int in sql?
    pub is_required_viewer: bool,
    pub name: String,
    pub user_id: i64
}


// #[derive(Clone, Debug, serde::Deserialize)]
#[derive(sqlx::FromRow)]
pub struct Message {
    pub id: i64,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub expire_at: Option<chrono::DateTime<chrono::Utc>>,
    pub is_public: bool,
    pub is_transient: bool,
    pub text: Option<String>,
    pub title: Option<String>,
    pub user_id: i64,
}


// #[derive(Clone, Debug, serde::Deserialize)]
#[derive(sqlx::FromRow)]
pub struct File {
    pub id: i64,
    pub file_name: String,
    pub message_id: i64,
}



// #[derive(Clone, Debug, serde::Deserialize)]
#[derive(sqlx::FromRow)]
pub struct Permission {
    pub message_id: i64,
    pub permissions: i64,  // TODO: flags?
    pub user_id: i64,
}


// #[derive(Clone, Debug, serde::Deserialize)]
#[derive(sqlx::FromRow)]
pub struct View {
    pub id: i64,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub device_id: i64,
    pub message_id: i64,
}
