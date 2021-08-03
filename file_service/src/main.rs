// BSD 3-Clause License
//
// Copyright (c) 2021, Lucina
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

use actix_web::http::header;
use actix_web::{delete, get, http, put, web, App, HttpMessage, HttpRequest, HttpResponse, HttpServer};
use shared::clients;
use shared::sql::Database;
mod files;
mod utility;
use openssl::ssl::{SslAcceptor, SslFiletype, SslMethod};
use shared::{dao_models, dto_models};


lazy_static::lazy_static! {
    static ref URL: String = shared::get_env_variable("FILE_SERVICE_ADDRESS")
        .map(shared::remove_protocol)
        .unwrap();
    static ref AUTH_URL: String = shared::get_env_variable("AUTH_SERVICE_ADDRESS").unwrap();
    static ref DATABASE_URL: String = shared::get_env_variable("DATABASE_URL").unwrap();
    static ref FILE_BASE_URL: String = shared::get_env_variable("FILE_BASE_URL").unwrap();
    static ref HOSTNAME: String = shared::get_env_variable("FILE_SERVICE_HOSTNAME").unwrap();
    static ref SSL_KEY: String = shared::get_env_variable("FILE_SERVICE_KEY").unwrap();
    static ref SSL_CERT: String = shared::get_env_variable("FILE_SERVICE_CERT").unwrap();
}


#[inline]
fn content_disposition(filename: &str) -> (http::HeaderName, header::ContentDisposition) {
    let disposition = header::ContentDisposition {
        disposition: header::DispositionType::Inline, // TODO: inline or attachment?
        parameters:  vec![header::DispositionParam::FilenameExt(header::ExtendedValue {
            charset:      header::Charset::Ext("UTF-8".to_owned()),
            language_tag: None,
            value:        filename.as_bytes().to_owned()
        })]
    };
    (header::CONTENT_DISPOSITION, disposition)
}


#[delete("/messages/{message_id}/files/{file_name}")]
async fn delete_message_file(
    auth_handler: web::Data<Arc<dyn clients::Auth>>,
    db: web::Data<Arc<dyn Database>>,
    req: HttpRequest,
    path: web::Path<(uuid::Uuid, String)>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    let (message_id, file_name) = path.into_inner();

    let user = auth_handler
        .resolve_user(utility::get_auth_header(&req)?)
        .await
        .map_err(utility::map_auth_response)?;

    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "file")?;

    if user.id != message.user_id {
        return Err(utility::single_error(404, "File not found"));
    };

    // TODO: the actual file should be deleted by a CRON job at a later date
    match db.delete_file_by_name(&message_id, &file_name).await {
        Ok(true) => Ok(HttpResponse::NoContent().finish()),
        Ok(false) => Err(utility::single_error(404, "File not found")),
        Err(error) => {
            log::error!("Failed to delete file entry due to {:?}", error);
            Err(utility::single_error(500, "Failed to delete file"))
        }
    }
}


async fn read_file(
    file: &dao_models::File,
    file_name: &str,
    file_reader: &web::Data<Arc<dyn files::FileReader>>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    file_reader
        .read_file(file)
        .await
        .map(|value| {
            HttpResponse::Ok()
                .insert_header((header::CONTENT_TYPE, file.content_type.clone()))
                .insert_header(content_disposition(file_name))
                .body(value)
        })
        .map_err(|error| {
            log::error!("Failed to read file due to {:?}", error);
            utility::single_error(500, "Failed to load file's contents")
        })
}


#[get("/messages/{message_id}/files/{file_name}")]
async fn get_message_file(
    auth_handler: web::Data<Arc<dyn clients::Auth>>,
    db: web::Data<Arc<dyn Database>>,
    file_reader: web::Data<Arc<dyn files::FileReader>>,
    req: HttpRequest,
    path: web::Path<(uuid::Uuid, String)>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    let (message_id, file_name) = path.into_inner();

    let user = auth_handler
        .resolve_user(utility::get_auth_header(&req)?)
        .await
        .map_err(utility::map_auth_response)?;

    let file = utility::resolve_database_entry(db.get_file_by_name(&message_id, &file_name).await, "file")?;
    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "file")?;

    if user.id != message.user_id {
        return Err(utility::single_error(404, "File not found"));
    };

    read_file(&file, &file_name, &file_reader).await
}


#[get("/links/{link_token}/files/{file_name}")]
async fn get_shared_message_file(
    auth_handler: web::Data<Arc<dyn clients::Auth>>,
    db: web::Data<Arc<dyn Database>>,
    file_reader: web::Data<Arc<dyn files::FileReader>>,
    path: web::Path<(String, String)>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    let (token, file_name) = path.into_inner();

    let link = auth_handler
        .resolve_link(&token)
        .await
        .map_err(utility::map_auth_response)?;

    let file = utility::resolve_database_entry(db.get_file_by_name(&link.message_id, &file_name).await, "file")?;

    read_file(&file, &file_name, &file_reader).await
}


#[put("/messages/{message_id}/files/{file_name}")]
async fn put_message_file(
    auth_handler: web::Data<Arc<dyn clients::Auth>>,
    db: web::Data<Arc<dyn Database>>,
    file_reader: web::Data<Arc<dyn files::FileReader>>,
    req: HttpRequest,
    path: web::Path<(uuid::Uuid, String)>,
    data: web::Bytes // data: web::Payload,
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    let (message_id, file_name) = path.into_inner();
    let content_type = req.content_type();

    if file_name.len() > 120 {
        return Err(utility::single_error(
            400,
            "File name cannot be over 120 characters long"
        ));
    };

    if content_type.is_empty() {
        return Err(utility::single_error(400, "Missing content type header"));
    };

    let user = auth_handler
        .resolve_user(utility::get_auth_header(&req)?)
        .await
        .map_err(utility::map_auth_response)?;

    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "message")?;

    if user.id != message.user_id {
        return Err(utility::single_error(404, "Message not found"));
    };

    let location = format!(
        "{}/messages/{}/files/{}",
        *HOSTNAME,
        message_id,
        urlencoding::encode(&file_name)
    );
    save_file(&db, &file_reader, &message.id, &file_name, content_type, &data)
        .await
        .map(|value| {
            HttpResponse::Ok()
                .insert_header((header::LOCATION, location))
                .json(value)
        })
}


async fn save_file(
    db: &web::Data<Arc<dyn Database>>,
    file_reader: &web::Data<Arc<dyn files::FileReader>>,
    message_id: &uuid::Uuid,
    file_name: &str,
    content_type: &str,
    data: &[u8] // ) -> clients::RestResult<dto_models::File> {
) -> Result<dto_models::File, actix_web::error::InternalError<&'static str>> {
    let date = chrono::Utc::now();

    // We save the file before making an SQL entry as while an entry-less file will
    // be ignored and eventually garbage collected, a file-less SQL entry will
    // persist and lead to errors if it's looked up
    file_reader
        .save_file(&message_id, &date, file_name, data)
        .await
        .map_err(|error| {
            log::error!("Failed to save file due to {:?}", error);
            utility::single_error(500, "Internal server error")
        })?;

    db.set_or_update_file(&message_id, file_name, content_type, &date)
        .await
        .map(|value| dto_models::File::from_dao(value, &HOSTNAME))
        // TODO: should some cases of this actually be handled as the message not existing
        .map_err(|error| {
            log::error!("Failed to set file database entry due to {:?}", error);
            utility::single_error(500, "Internal server error")
        })
}


// #[actix_web::main]
async fn actix_main() -> std::io::Result<()> {
    let auth_handler = clients::AuthClient::new(&AUTH_URL);
    let file_reader = files::LocalReader::new(&FILE_BASE_URL);
    let pool = shared::postgres::Pool::connect(&DATABASE_URL).await.unwrap();

    let mut ssl_acceptor = SslAcceptor::mozilla_intermediate(SslMethod::tls_server()).unwrap();
    ssl_acceptor.set_private_key_file(&*SSL_KEY, SslFiletype::PEM).unwrap();
    ssl_acceptor.set_certificate_chain_file(&*SSL_CERT).unwrap();

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(Arc::from(auth_handler.clone()) as Arc<dyn clients::Auth>))
            .app_data(web::Data::new(Arc::from(pool.clone()) as Arc<dyn Database>))
            .app_data(web::Data::new(
                Arc::from(file_reader.clone()) as Arc<dyn files::FileReader>
            ))
            .app_data(web::PayloadConfig::new(209_715_200)) // TODO: decide on size
            .service(delete_message_file)
            .service(get_message_file)
            .service(get_shared_message_file)
            .service(put_message_file)
    })
    .server_hostname(&*HOSTNAME)
    .bind_openssl(&*URL, ssl_acceptor)?
    .run()
    .await
}

fn main() -> std::io::Result<()> {
    shared::setup_logging();
    actix_web::rt::System::with_tokio_rt(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .unwrap()
    })
    .block_on(actix_main())
}
