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

use actix_web::{get, http, patch, put, web, App, HttpRequest, HttpResponse, HttpServer};
use shared::dto_models;
use shared::sql::{Database, DatabaseResult, SetError};

mod crypto;
use crypto::Hasher;

pub fn single_error(status: u16, detail: &str) -> HttpResponse {
    let response =
        dto_models::ErrorsResponse::default().with_error(dto_models::Error::default().status(status).detail(detail));

    HttpResponse::build(http::StatusCode::from_u16(status).unwrap()).json(response)
}


pub fn resolve_database_entry<T>(result: DatabaseResult<T>, resource_name: &str) -> Result<T, HttpResponse> {
    match result {
        Ok(Some(entry)) => Ok(entry),
        Ok(None) => Err(single_error(404, &format!("{} not found", resource_name))),
        Err(error) => {
            log::error!("Failed to get entry from SQL database due to {}", error);

            Err(single_error(500, "Database lookup failed"))
        }
    }
}


async fn resolve_user(
    req: &HttpRequest,
    db: &web::Data<Arc<dyn Database>>,
    hasher: &web::Data<Arc<dyn Hasher>>
) -> Result<shared::dao_models::User, HttpResponse> {
    let value = req
        .headers()
        .get(http::header::AUTHORIZATION)
        .ok_or_else(|| single_error(401, "Missing authorization header"))?
        .to_str()
        .map_err(|_| single_error(400, "Invalid authorization header"))?
        .to_owned();

    if value.len() < 7 {
        return Err(single_error(400, "Invalid authorization header"));
    }

    let (token_type, token) = value.split_at(6);

    if !"Basic ".eq_ignore_ascii_case(token_type) {
        return Err(single_error(401, "Expected a Basic authorization token"));
    }

    let token = sodiumoxide::base64::decode(token, sodiumoxide::base64::Variant::Original)
        .map_err(|_| single_error(400, "Invalid authorization header"))?;
    let (username, password) = std::str::from_utf8(&token)
        .map_err(|_| single_error(400, "Invalid authorization header"))
        .and_then(|value| {
            let mut iterator = value.splitn(2, ':');
            match (iterator.next(), iterator.next()) {
                (Some(username), Some(password)) if !password.is_empty() => Ok((username, password)),
                _ => Err(single_error(400, "Invalid authorization header"))
            }
        })?;


    match db.get_user_by_username(username).await {
        Ok(Some(user)) => match hasher.verify(&user.password_hash, &password).await {
            Ok(true) => Ok(user),
            Ok(false) => Err(single_error(401, "Incorrect username or password")),
            other => {
                log::error!("Failed to check password due to {:?}", other);
                Err(single_error(500, "Internal server error"))
            }
        },
        Ok(None) => Err(single_error(401, "Incorrect username or password")),
        Err(error) => {
            log::error!("Failed to get user from database due to {}", error);
            Err(single_error(400, "Internal server error"))
        }
    }
}


#[get("/users/@me")]
async fn get_current_user(
    req: HttpRequest,
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>
) -> Result<HttpResponse, HttpResponse> {
    resolve_user(&req, &db, &hasher)
        .await
        .map(shared::dto_models::User::from_dao)
        .map(|v| HttpResponse::Ok().json(v))
}

#[put("/users/{username}")]
async fn put_user(
    req: HttpRequest,
    username: web::Path<String>,
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>,
    user: web::Json<dto_models::ReceivedUser>
) -> Result<HttpResponse, HttpResponse> {
    let username = username.into_inner();
    resolve_user(&req, &db, &hasher).await?; // TODO: check flags

    let password_hash = hasher.hash(&user.password).await.map_err(|e| {
        log::error!("Failed to hash password due to {:?}", e);
        single_error(500, "Internal server error")
    })?;

    let result = db.set_user(&user.flags, &password_hash, &username).await;

    match result {
        Ok(user) => Ok(HttpResponse::Ok().json(dto_models::User::from_dao(user))),
        Err(SetError::Conflict) => Err(single_error(409, "User already exists")),
        Err(SetError::Unknown(error)) => {
            log::error!("Failed to set user due to {:?}", error);
            Err(single_error(500, "Internal server error"))
        }
    }
}


#[patch("/users/@me")]
async fn patch_user(
    req: HttpRequest,
    db: web::Data<Arc<dyn Database>>,
    hasher: web::Data<Arc<dyn Hasher>>,
    user_update: web::Json<dto_models::UserUpdate>
) -> Result<HttpResponse, HttpResponse> {
    let user = resolve_user(&req, &db, &hasher).await?;

    let password_hash = match &user_update.password {
        Some(password) => hasher.hash(&password).await.map(Some).map_err(|e| {
            log::error!("Failed to hash password due to {:?}", e);
            single_error(500, "Internal server error")
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
            single_error(500, "Internal server error")
        })?;

    match result {
        Some(result) => Ok(HttpResponse::Ok().json(dto_models::User::from_dao(result))),
        // TODO: this shouldn't actually ever happen outside of maybe a few race conditions
        None => Err(single_error(404, "Couldn't find user"))
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
            .service(get_current_user)
            .service(patch_user)
            .service(put_user)
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
