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

use actix_web::{get, web, App, HttpResponse, HttpServer};

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


fn resolve_database_entry<T>(result: DatabaseResult<T>, resource_name: &str) -> Result<T, HttpResponse> {
    match result {
        Ok(Some(entry)) => Ok(entry),
        Ok(None) => {
            let response = errors::ErrorsResponse::new().with_error(
                errors::Error::new()
                    .status(404)
                    .detail(&format!("{} not found", resource_name))
            );
            Err(HttpResponse::NotFound().json(response))
        }
        Err(error) => {
            log::error!(
                "Failed to get {} entry from SQL database due to {}",
                resource_name,
                error
            );
            let response = errors::ErrorsResponse::new()
                .with_error(errors::Error::new().status(500).detail("Database lookup failed"));

            Err(HttpResponse::InternalServerError().json(response))
        }
    }
}


#[get("/{message_id}/{file_name}")]
async fn get_message_file(
    db: web::Data<Arc<dyn Database>>,
    file_reader: web::Data<Arc<dyn files::FileReader>>,
    path: web::Path<(i64, String)>
) -> Result<HttpResponse, HttpResponse> {
    let (message_id, file_name) = path.into_inner();

    let file = resolve_database_entry(db.get_file(&message_id, &file_name).await, "file")?;

    if !file.is_public {}; // TODO: all the access checks

    match file_reader.read_file(&file).await {
        Ok(file_contents) => Ok(HttpResponse::Ok().body(file_contents)),
        Err(error) => {
            log::error!("Failed to read file due to {}", error);
            let response = errors::ErrorsResponse::new().with_error(
                errors::Error::new()
                    .status(500)
                    .detail("Failed to load file's contents")
            );

            Err(HttpResponse::InternalServerError().json(response))
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
            .service(get_message_file)
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
