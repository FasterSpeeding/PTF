#![feature(decl_macro)]
#[macro_use] extern crate dotenv_codegen;
#[macro_use] extern crate rocket;
use sqlx;


// use bb8_postgres::bb8;
// #[macro_use] extern crate rocket_contrib;

mod sql;


#[get("/<message_id>/<filename>")]
async fn get_file(
    conn: Box<dyn sql::traits::Database>, message_id: i64, filename: String
) -> Result<String, ()> {
    let user = conn.get_user_by_id(&1).await.unwrap().unwrap();
    return Ok(user.username);
}


#[launch]
async fn launch() -> rocket::Rocket {
    let url = dotenv!("database_url");
    let pool = sql::app::Pool::<sqlx::Postgres>::connect(url).await;
    return rocket::ignite()
        .attach::<Box<dyn sql::traits::Database>>(Box::new(pool))
        .mount("/", routes![get_file]);
}
