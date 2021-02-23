#![feature(associated_type_bounds)]
#[macro_use] extern crate dotenv_codegen;
use actix_web::{get, web, App, HttpServer, Responder};
use coi::container;
use coi_actix_web::inject;
use sqlx;


// use bb8_postgres::bb8;
// #[macro_use] extern crate rocket_contrib;

mod sql;
use sql::traits::Database;


#[get("/<message_id>/<filename>")]
async fn get_file(
    #[inject] conn: Box<dyn Database>, message_id: i64, filename: String
) -> Result<String, ()> {
    let user = conn.get_user_by_id(&1).await.unwrap().unwrap();
    return Ok(user.username);
}


#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let url = dotenv!("DATABASE_URL");
    let raw_pool = std::sync::Arc::new(sqlx::PgPool::connect(url).await.unwrap());
    let pool = sql::app::Pool::new(raw_pool);
    
    let container = container! {
        DatabaseProvider => sql::app::PoolProvider,
    };
    
    return HttpServer::new(move || {
        App::new()
            .app_data(container.clone())
            .service(get_file)}
    )
        .bind("127.0.0.1:8080")?
        .run()
        .await;
}
