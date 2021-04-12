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

use actix_web::{delete, get, patch, post, web, App, HttpRequest, HttpResponse, HttpServer};
use shared::dto_models;
use shared::sql::{Database, SetError};
use validator::Validate;

mod crypto;
use crypto::Hasher;
mod utility;


#[delete("/users/@me")]
async fn delete_current_user(
    req: HttpRequest,
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>
) -> Result<HttpResponse, HttpResponse> {
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
    req: HttpRequest,
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>
) -> Result<HttpResponse, HttpResponse> {
    utility::resolve_user(&req, &db, &hasher)
        .await
        .map(shared::dto_models::User::from_auth)
        .map(|v| HttpResponse::Ok().json(v))
}


#[post("/users")]
async fn post_user(
    // TODO: refactor this so it's less internal info leaky
    req: HttpRequest,
    user: web::Json<dto_models::ReceivedUser>,
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>
) -> Result<HttpResponse, HttpResponse> {
    // TODO: remove "id" from some responses
    if let Err(error) = user.validate() {
        let response = dto_models::Error::from_validation_errors(&error);
        return Err(HttpResponse::BadRequest().json(response));
    };

    utility::resolve_flags(&req, &db, &hasher, 1 << 2).await?;

    let password_hash = hasher.hash(&user.password).await.map_err(|e| {
        log::error!("Failed to hash password due to {:?}", e);
        utility::single_error(500, "Internal server error")
    })?;

    let result = db.set_user(&user.flags, &password_hash, &user.username).await;

    match result {
        Ok(user) => Ok(HttpResponse::Ok().json(dto_models::User::from_auth(user))),
        Err(SetError::Conflict) => Err(utility::single_error(409, "User already exists")),
        Err(SetError::Unknown(error)) => {
            log::error!("Failed to set user due to {:?}", error);
            Err(utility::single_error(500, "Internal server error"))
        }
    }
}


#[patch("/users/@me")]
async fn patch_current_user(
    req: HttpRequest,
    user_update: web::Json<dto_models::UserUpdate>,
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>
) -> Result<HttpResponse, HttpResponse> {
    // TODO: remove "id" from some responses
    if let Err(error) = user_update.validate() {
        let response = dto_models::Error::from_validation_errors(&error);
        return Err(HttpResponse::BadRequest().json(response));
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
            &password_hash.as_deref(),
            &user_update.username.as_deref()
        )
        .await
        .map_err(|e| {
            log::error!("Failed to update user due to {:?}", e);
            utility::single_error(500, "Internal server error")
        })?;

    match result {
        Some(result) => Ok(HttpResponse::Ok().json(dto_models::User::from_auth(result))),
        // TODO: this shouldn't actually ever happen outside of maybe a few race conditions
        None => Err(utility::single_error(404, "Couldn't find user"))
    }
}


#[get("/messages/{message_id}/links")]
async fn get_message_link(
    message_id: web::Path<uuid::Uuid>,
    link: web::Query<dto_models::LinkQuery>, // TODO: remove "id" from some responses
    db: web::Data<Arc<dyn Database>>
) -> Result<HttpResponse, HttpResponse> {
    let message_id = message_id.into_inner();
    let link = link.into_inner();

    db.get_message_link(&message_id, &link.token)
        .await
        .map_err(|e| {
            log::error!("Failed to get message link from db due to {:?}", e);
            utility::single_error(500, "Internal server error")
        })
        .map(|v| match v {
            Some(link) if link.message_id == message_id => HttpResponse::Ok().json(link),
            _ => utility::single_error(404, "Link not found")
        })
}


#[post("/users/@me/messages/{message_id}/links")]
async fn post_my_message_link(
    req: HttpRequest,
    message_id: web::Path<uuid::Uuid>,
    message_link: web::Json<dto_models::ReceivedMessageLink>,
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>
) -> Result<HttpResponse, HttpResponse> {
    let message_id = message_id.into_inner();
    let user = utility::resolve_user(&req, &db, &hasher).await?;
    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "message")?;

    if message.user_id != user.id {
        return Err(utility::single_error(404, "Message not found"));
    };

    let result = db
        .set_message_link(
            &crypto::gen_link_key(),
            &message_link.access,
            &message_link.expires_at,
            &message_id,
            &message_link.resource
        )
        .await;
    match result {
        Ok(link) => Ok(HttpResponse::Ok().json(link)),
        Err(error) => {
            log::error!("Failed to set message link due to {:?}", error);
            Err(utility::single_error(500, "Internal server error"))
        }
    }
}


#[delete("/users/@me/messages/{message_id}/links")]
async fn delete_my_message_link(
    req: HttpRequest,
    link: web::Query<dto_models::LinkQuery>, // TODO: remove "id" from some responses
    message_id: web::Path<uuid::Uuid>,
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>
) -> Result<HttpResponse, HttpResponse> {
    let link = link.into_inner();
    let message_id = message_id.into_inner();
    let user = utility::resolve_user(&req, &db, &hasher).await?;
    let message = utility::resolve_database_entry(db.get_message(&message_id).await, "message")?;

    if message.user_id != user.id {
        return Err(utility::single_error(404, "Message not found"));
    };

    match db.delete_message_link(&message_id, &link.token).await {
        Ok(true) => Ok(HttpResponse::NoContent().finish()),
        Ok(false) => Err(utility::single_error(404, "Message link not found")),
        Err(error) => {
            log::error!("Failed to delete link entry due to {:?}", error);
            Err(utility::single_error(500, "Failed to delete link"))
        }
    }
}


// #[actix_web::main]
async fn actix_main() -> std::io::Result<()> {
    let url = shared::get_env_variable("AUTH_SERVICE_ADDRESS")
        .map(shared::remove_protocol)
        .unwrap();
    let database_url = shared::get_env_variable("DATABASE_URL").unwrap();
    let pool = shared::postgres::Pool::connect(&database_url).await.unwrap();
    let hasher = crypto::Argon::new();

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(Arc::from(pool.clone()) as Arc<dyn Database>))
            .app_data(web::Data::new(Arc::from(hasher.clone()) as Arc<dyn Hasher>))
            .service(delete_current_user)
            .service(delete_my_message_link)
            .service(get_current_user)
            .service(get_message_link)
            .service(patch_current_user)
            .service(post_my_message_link)
            .service(post_user)
    })
    .bind(url)?
    .run()
    .await
}

fn main() {
    shared::setup_logging();
    sodiumoxide::init().unwrap();
    actix_web::rt::System::with_tokio_rt(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .unwrap()
    })
    .block_on(actix_main())
    .unwrap();
}
