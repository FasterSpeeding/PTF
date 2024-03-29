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

use actix_web::{delete, get, patch, post, web, App, HttpRequest, HttpResponse, HttpServer};
use openssl::ssl::{SslAcceptor, SslFiletype, SslMethod};
use shared::dto_models;
use shared::sql::{Database, SetError};
use validator::Validate;

mod crypto;
use crypto::Hasher;
mod utility;


lazy_static::lazy_static! {
    static ref HOSTNAME: String = shared::get_env_variable("AUTH_SERVICE_HOSTNAME").unwrap();
    static ref URL: String = shared::get_env_variable("AUTH_SERVICE_ADDRESS")
        .map(shared::remove_protocol)
        .unwrap();
    static ref DATABASE_URL: String = shared::get_env_variable("DATABASE_URL").unwrap();
    static ref SSL_KEY: String = shared::get_env_variable("AUTH_SERVICE_KEY").unwrap();
    static ref SSL_CERT: String = shared::get_env_variable("AUTH_SERVICE_CERT").unwrap();
}


#[delete("/users/@me")]
async fn delete_current_user(
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>,
    req: HttpRequest
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    let user = utility::resolve_user(&req, &db, &hasher).await?;

    match db.delete_user(&user.id).await {
        Ok(true) => Ok(HttpResponse::NoContent().finish()),
        Ok(false) => Err(utility::single_error(404, "User not found")),
        Err(error) => {
            log::error!("Failed to delete user entry due to {:?}", error);
            Err(utility::single_error(500, "Failed to delete user"))
        }
    }
}


#[get("/users/@me")]
async fn get_current_user(
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>,
    req: HttpRequest
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    utility::resolve_user(&req, &db, &hasher)
        .await
        .map(shared::dto_models::User::from_dao)
        .map(|v| HttpResponse::Ok().json(v))
}


#[post("/users")]
async fn post_user(
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>,
    req: HttpRequest,
    user: web::Json<dto_models::ReceivedUser>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    if let Err(error) = user.validate() {
        return Ok(HttpResponse::BadRequest().json(error)); // TODO: Err?
    };

    utility::resolve_flags(&req, &db, &hasher, 1 << 2).await?;

    let password_hash = hasher.hash(&user.password).await.map_err(|error| {
        log::error!("Failed to hash password due to {:?}", error);
        utility::single_error(500, "Internal server error")
    })?;

    let result = db
        .set_user(&uuid::Uuid::new_v4(), &user.flags, &password_hash, &user.username)
        .await;

    match result {
        // TODO: get current user as Location?
        Ok(user) => Ok(HttpResponse::Created().json(dto_models::User::from_dao(user))),
        Err(SetError::Conflict) => Err(utility::single_error(403, "User already exists")),
        Err(SetError::Unknown(error)) => {
            log::error!("Failed to set user due to {:?}", error);
            Err(utility::single_error(500, "Internal server error"))
        }
    }
}


#[patch("/users/@me")]
async fn patch_current_user(
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>,
    req: HttpRequest,
    user_update: web::Json<dto_models::UserUpdate>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    if let Err(error) = user_update.validate() {
        return Ok(HttpResponse::BadRequest().json(error)); // TODO: Err?
    };

    let user = utility::resolve_user(&req, &db, &hasher).await?;

    let password_hash = match &user_update.password {
        Some(password) => hasher.hash(password).await.map(Some).map_err(|e| {
            log::error!("Failed to hash password due to {:?}", e);
            utility::single_error(500, "Internal server error")
        })?,
        None => None
    };

    let result = db
        .update_user(
            &user.id,
            &user_update.flags,
            password_hash.as_deref(),
            user_update.username.as_deref()
        )
        .await;

    match result {
        Err(error) => {
            log::error!("Failed to update user due to {:?}", error);
            Err(utility::single_error(500, "Internal server error"))
        }
        Ok(Some(value)) => Ok(HttpResponse::Ok().json(dto_models::User::from_dao(value))),
        // TODO: this shouldn't actually ever happen outside of maybe a few race conditions
        Ok(None) => Err(utility::single_error(404, "Couldn't find user"))
    }
}


#[get("/links/{link_token}")]
async fn get_message_link(
    db: web::Data<Arc<dyn Database>>,
    path: web::Path<String>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    match db.get_message_link(&path.into_inner()).await {
        Err(error) => {
            log::error!("Failed to get message link from db due to {:?}", error);
            Err(utility::single_error(500, "Internal server error"))
        }
        Ok(Some(value)) => Ok(HttpResponse::Ok().json(dto_models::MessageLink::from_dao(value))),
        Ok(None) => Err(utility::single_error(404, "Link not found"))
    }
}


#[delete("/messages/{message_id}/links/{link}")]
async fn delete_message_link(
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>,
    req: HttpRequest,
    path: web::Path<(uuid::Uuid, String)>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    let (message_id, link) = path.into_inner();
    let user = utility::resolve_user(&req, &db, &hasher).await?;
    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "message")?;

    if message.user_id != user.id {
        return Err(utility::single_error(404, "Message not found"));
    };

    match db.delete_message_link(&message_id, &link).await {
        Ok(true) => Ok(HttpResponse::NoContent().finish()),
        Ok(false) => Err(utility::single_error(404, "Message link not found")),
        Err(error) => {
            log::error!("Failed to delete link entry due to {:?}", error);
            Err(utility::single_error(500, "Failed to delete link"))
        }
    }
}


#[get("/messages/{message_id}/links")]
async fn get_message_links(
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>,
    req: HttpRequest,
    message_id: web::Path<uuid::Uuid>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    let message_id = message_id.into_inner();
    let user = utility::resolve_user(&req, &db, &hasher).await?;

    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "message")?;

    if message.user_id != user.id {
        return Err(utility::single_error(404, "Message not found"));
    };

    db.get_message_links(&message_id)
        .await
        .map(|mut value| {
            value
                .drain(..)
                .map(dto_models::MessageLink::from_dao)
                .collect::<Vec<_>>()
        })
        .map(|value| HttpResponse::Ok().json(value))
        .map_err(|error| {
            log::error!("Failed to get message links from database due to {:?}", error);
            utility::single_error(500, "Failed to delete link")
        })
}


#[post("/messages/{message_id}/links")]
async fn post_message_link(
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>,
    req: HttpRequest,
    message_id: web::Path<uuid::Uuid>,
    received_link: web::Json<dto_models::ReceivedMessageLink>
) -> Result<HttpResponse, actix_web::error::InternalError<&'static str>> {
    let message_id = message_id.into_inner();
    let user = utility::resolve_user(&req, &db, &hasher).await?;
    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "message")?;

    if message.user_id != user.id {
        return Err(utility::single_error(404, "Message not found"));
    };


    let token = crypto::gen_link_key();
    let location = format!("{}/messages/{}/links/{}", *HOSTNAME, message_id, token);

    db.set_message_link(
        &message_id,
        &token,
        &received_link.access,
        &received_link.expire_after.map(|value| chrono::Utc::now() + value),
        received_link.resource.as_deref()
    )
    .await
    .map(dto_models::MessageLink::from_dao)
    .map(|value| utility::with_location(&mut HttpResponse::Created(), &location).json(value))
    .map_err(|error| {
        log::error!("Failed to set message link due to {:?}", error);
        utility::single_error(500, "Internal server error")
    })
}


// #[actix_web::main]
async fn actix_main() -> std::io::Result<()> {
    let pool = shared::postgres::Pool::connect(&DATABASE_URL).await.unwrap();
    let hasher = crypto::Argon::new();

    let mut ssl_acceptor = SslAcceptor::mozilla_intermediate(SslMethod::tls_server()).unwrap();
    ssl_acceptor.set_private_key_file(&*SSL_KEY, SslFiletype::PEM).unwrap();
    ssl_acceptor.set_certificate_chain_file(&*SSL_CERT).unwrap();

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(Arc::from(pool.clone()) as Arc<dyn Database>))
            .app_data(web::Data::new(Arc::from(hasher.clone()) as Arc<dyn Hasher>))
            .service(delete_current_user)
            .service(delete_message_link)
            .service(get_current_user)
            .service(get_message_links)
            .service(get_message_link)
            .service(patch_current_user)
            .service(post_message_link)
            .service(post_user)
    })
    .bind_openssl(&*URL, ssl_acceptor)?
    .run()
    .await
}

fn main() -> std::io::Result<()> {
    shared::setup_logging();
    sodiumoxide::init().unwrap();
    actix_web::rt::System::with_tokio_rt(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .unwrap()
    })
    .block_on(actix_main())
}
