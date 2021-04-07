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
use std::sync::Arc;

use actix_web::{delete, get, http, put, web, App, HttpMessage, HttpRequest, HttpResponse, HttpServer};
use shared::sql::Database;
mod auth;
mod files;
mod utility;


#[delete("/users/@me/messages/{message_id}/files/{file_name}")]
async fn delete_my_message_file(
    req: HttpRequest,
    path: web::Path<(uuid::Uuid, String)>,
    auth_handler: web::Data<Arc<dyn auth::Auth>>,
    db: web::Data<Arc<dyn Database>>,
    file_reader: web::Data<Arc<dyn files::FileReader>>
) -> Result<HttpResponse, HttpResponse> {
    let (message_id, file_name) = path.into_inner();
    let file_name = file_reader.process_name(file_name)?;

    let user = auth_handler
        .resolve_user(auth::get_auth_header(&req)?)
        .await
        .map_err(|e| {
            log::error!("Failed to check authorization due to {:?}", e);
            utility::single_error(500, "Internal server error")
        })?;

    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "file")?;

    if user.id != message.user_id {
        return Err(utility::single_error(404, "File not found"));
    };

    // TODO: the actual file should be deleted by a CRON job at a later date
    match db.delete_file(&message_id, &file_name).await {
        // TODO: normalised file name
        Ok(true) => Ok(HttpResponse::NoContent().finish()),
        Ok(false) => Err(utility::single_error(404, "File not found")),
        Err(error) => {
            log::error!("Failed to delete file entry due to {:?}", error);
            Err(utility::single_error(404, "Failed to delete file"))
        }
    }
}


#[get("/users/@me/messages/{message_id}/files/{file_name}")]
async fn get_my_message_file(
    req: HttpRequest,
    path: web::Path<(uuid::Uuid, String)>,
    auth_handler: web::Data<Arc<dyn auth::Auth>>,
    db: web::Data<Arc<dyn Database>>,
    file_reader: web::Data<Arc<dyn files::FileReader>>
) -> Result<HttpResponse, HttpResponse> {
    let (message_id, file_name) = path.into_inner();
    let file_name = file_reader.process_name(file_name)?;

    let user = auth_handler
        .resolve_user(auth::get_auth_header(&req)?)
        .await
        .map_err(|e| {
            log::error!("Failed to check authorization due to {:?}", e);
            utility::single_error(500, "Internal server error")
        })?;

    let file = utility::resolve_database_entry(db.get_file(&message_id, &file_name).await, "file")?;
    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "file")?;

    if user.id != message.user_id {
        return Err(utility::single_error(404, "File not found"));
    };

    match file_reader.read_file(&file).await {
        Ok(file_contents) => Ok(HttpResponse::Ok()
            .append_header((http::header::CONTENT_TYPE, file.content_type))
            .body(file_contents)),
        Err(error) => {
            log::error!("Failed to read file due to {:?}", error);
            Err(utility::single_error(500, "Failed to load file's contents"))
        }
    }
}


#[put("/users/@me/messages/{message_id}/files/{file_name}")]
async fn put_my_message_file(
    req: HttpRequest,
    path: web::Path<(uuid::Uuid, String)>,
    data: actix_web::web::Bytes,
    // data: actix_web::web::Payload,
    db: web::Data<Arc<dyn Database>>,
    file_reader: web::Data<Arc<dyn files::FileReader>>
) -> Result<HttpResponse, HttpResponse> {
    let (message_id, file_name) = path.into_inner();
    let file_name = file_reader.process_name(file_name)?;

    let content_type = req.content_type();
    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "file")?;

    // We save the file before making an SQL entry as while an entry-less file will
    // ignored and eventually garbage collected, a file-less SQL entry will persist
    // and lead to errors if it's looked up
    file_reader
        .save_file(&message.id, &file_name, &data)
        .await
        .map_err(|e| {
            log::error!("Failed to save file due to {:?}", e);
            utility::single_error(500, "Internal server error")
        })?;

    let result = db
        .set_or_update_file(&message.id, &file_name, &content_type)
        .await
        // TODO: should some cases of this actually be handled as the message not existing
        .map_err(|e| {
            log::error!("Failed to set file database entry due to {:?}", e);
            utility::single_error(500, "Internal server error")
        })?;

    Ok(HttpResponse::Ok().json(result))
}


// #[actix_web::main]
async fn actix_main() -> std::io::Result<()> {
    let url = shared::get_env_variable("FILE_SERVICE_ADDRESS")
        .map(shared::remove_protocol)
        .unwrap();
    let auth_url = shared::get_env_variable("AUTH_SERVICE_ADDRESS").unwrap();
    let database_url = shared::get_env_variable("DATABASE_URL").unwrap();
    let file_base_url = shared::get_env_variable("FILE_BASE_URL").unwrap();
    let auth_handler = auth::AuthClient::new(&auth_url);
    let file_reader = files::LocalReader::new(&file_base_url);
    let pool = shared::postgres::Pool::connect(&database_url).await.unwrap();

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(Arc::from(auth_handler.clone()) as Arc<dyn auth::Auth>))
            .app_data(web::Data::new(Arc::from(pool.clone()) as Arc<dyn Database>))
            .app_data(web::Data::new(
                Arc::from(file_reader.clone()) as Arc<dyn files::FileReader>
            ))
            .service(delete_my_message_file)
            .service(get_my_message_file)
            .service(put_my_message_file)
    })
    .bind(url)?
    .run()
    .await
}

fn main() {
    shared::setup_logging();
    actix_web::rt::System::with_tokio_rt(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .unwrap()
    })
    .block_on(actix_main())
    .unwrap();
}
