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
#![allow(dead_code)]
#[macro_use]
extern crate dotenv_codegen;
use std::sync::Arc;

use actix_web::{delete, get, http, put, web, App, HttpRequest, HttpResponse, HttpServer};
use argon2::PasswordVerifier;

mod sql;
use sql::traits::{Database, DatabaseResult};
mod errors;
mod files;


fn setup_logging(level: &str) {
    let level = match level.to_uppercase().as_str() {
        "TRACE" => log::LevelFilter::Trace,
        "DEBUG" => log::LevelFilter::Debug,
        "INFO" => log::LevelFilter::Info,
        "WARN" => log::LevelFilter::Warn,
        "ERROR" => log::LevelFilter::Error,
        _ => panic!("Invalid log level provided, expected TRACE, DEBUG, INFO, WARN or ERROR")
    };

    simple_logger::SimpleLogger::new().with_level(level).init().unwrap();
}


fn single_error(status: u16, detail: &str) -> HttpResponse {
    let response = errors::ErrorsResponse::new().with_error(errors::Error::new().status(status).detail(detail));

    HttpResponse::build(http::StatusCode::from_u16(status).unwrap()).json(response)
}


fn resolve_database_entry<T>(result: DatabaseResult<T>, resource_name: &str) -> Result<T, HttpResponse> {
    match result {
        Ok(Some(entry)) => Ok(entry),
        Ok(None) => Err(single_error(404, &format!("{} not found", resource_name))),
        Err(error) => {
            log::error!("Failed to get entry from SQL database due to {}", error);

            Err(single_error(500, "Database lookup failed"))
        }
    }
}

// TODO: use actix-web-httpauth here when actix-web 4.0.0 releases
async fn resolve_user(
    req: &HttpRequest,
    db: &web::Data<Arc<dyn Database>>
) -> Result<sql::dao_models::User, HttpResponse> {
    let value = req.headers().get(http::header::AUTHORIZATION).ok_or_else(|| {
        let response = errors::ErrorsResponse::new()
            .with_error(errors::Error::new().status(401).detail("Missing authorization header"));
        HttpResponse::Unauthorized().json(response)
    })?;

    let binary = base64::decode(value).map_err(|_| single_error(400, "Invalid authorization header"))?;

    let (username, password) = std::str::from_utf8(&binary)
        .ok()
        .and_then(|v| {
            let mut iterator = v.splitn(2, ':');
            match (iterator.next(), iterator.next()) {
                (Some(username), Some(password)) => Some((username, password)),
                _ => None
            }
        })
        .ok_or_else(|| single_error(400, "Invalid authorization header"))?;

    match db.get_user_by_username(username).await {
        Ok(Some(user)) => {
            let hash = argon2::PasswordHash::new(&user.password_hash).map_err(|e| {
                log::error!("Failed to parse stored password hash on {} due to {}", user.username, e);
                single_error(400, "Internal server error")
            })?;

            argon2::Argon2::default()
                .verify_password(password.as_bytes(), &hash)
                .map_err(|_| single_error(401, "Incorrect username or password"))?;

            Ok(user)
        }
        Ok(None) => Err(single_error(401, "Incorrect username or password")),
        Err(error) => {
            log::error!("Failed to get user from database due to {}", error);
            Err(single_error(400, "Internal server error"))
        }
    }
}


#[delete("/users/@me/messages/{message_id}/files/{file_name}")]
async fn delete_my_message_file(
    req: HttpRequest,
    db: web::Data<Arc<dyn Database>>,
    path: web::Path<(i64, String)>
) -> Result<HttpResponse, HttpResponse> {
    let (message_id, file_name) = path.into_inner();

    let user = resolve_user(&req, &db).await?;
    let message = resolve_database_entry(db.get_message(&message_id).await, "file")?;

    if user.id != message.user_id {
        return Err(single_error(404, "File not found"));
    };

    // TODO: the actual file should be deleted by a CRON job at a later date
    match db.delete_file(&message_id, &file_name).await {
        // TODO: normalised file name
        Ok(true) => Ok(HttpResponse::NoContent().finish()),
        Ok(false) => Err(single_error(404, "File not found")),
        Err(error) => {
            log::error!("Failed to delete file entry due to {}", error);
            Err(single_error(404, "Failed to delete file"))
        }
    }
}


#[get("/users/@me/messages/{message_id}/files/{file_name}")]
async fn get_my_message_file(
    req: HttpRequest,
    path: web::Path<(i64, String)>,
    db: web::Data<Arc<dyn Database>>,
    file_reader: web::Data<Arc<dyn files::FileReader>>
) -> Result<HttpResponse, HttpResponse> {
    let (message_id, file_name) = path.into_inner();

    let file = resolve_database_entry(db.get_file(&message_id, &file_name).await, "file")?;
    let user = resolve_user(&req, &db).await?;
    let message = resolve_database_entry(db.get_message(&message_id).await, "file")?;

    if user.id != message.user_id {
        return Err(single_error(404, "File not found"));
    };

    match file_reader.read_file(&file).await {
        Ok(file_contents) => Ok(HttpResponse::Ok().body(file_contents)),
        Err(error) => {
            log::error!("Failed to read file due to {}", error);
            Err(single_error(500, "Failed to load file's contents"))
        }
    }
}


// #[actix_web::main]
async fn actix_main() -> std::io::Result<()> {
    let url = dotenv!("DATABASE_URL");
    let file_reader = files::LocalReader::new(dotenv!("BASE_URL"));
    let pool = sql::app::Pool::new(sqlx::PgPool::connect(url).await.unwrap());

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(Arc::from(pool.clone()) as Arc<dyn Database>))
            .app_data(web::Data::new(
                Arc::from(file_reader.clone()) as Arc<dyn files::FileReader>
            ))
            .service(delete_my_message_file)
            .service(get_my_message_file)
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}

fn main() {
    setup_logging("DEBUG");
    actix_web::rt::System::with_tokio_rt(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .unwrap()
    })
    .block_on(actix_main())
    .unwrap();
}
