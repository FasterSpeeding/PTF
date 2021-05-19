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

use actix_web::{http, web, HttpRequest, HttpResponse};
use crypto::Hasher;
use shared::dto_models;
use shared::sql::{Database, DatabaseResult};

use crate::crypto;

pub fn single_error(status: u16, detail: &str) -> HttpResponse {
    let response =
        dto_models::ErrorsResponse::default().with_error(dto_models::Error::default().status(status).detail(detail));

    HttpResponse::build(http::StatusCode::from_u16(status).unwrap()).json(response)
}


pub fn with_location<'a>(
    builder: &'a mut actix_web::dev::HttpResponseBuilder,
    location: &str
) -> &'a mut actix_web::dev::HttpResponseBuilder {
    builder
        .insert_header((http::header::CONTENT_LOCATION, location))
        .insert_header((http::header::LOCATION, location))
}


pub fn unauthorized_error(detail: &str) -> HttpResponse {
    let response = dto_models::ErrorsResponse::default().with_error(
        dto_models::Error::default()
            .status(http::StatusCode::UNAUTHORIZED.as_u16())
            .detail(detail)
    );

    HttpResponse::Unauthorized()
        .insert_header((http::header::WWW_AUTHENTICATE, "Basic"))
        .json(response)
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


pub async fn resolve_user(
    req: &HttpRequest,
    db: &web::Data<Arc<dyn Database>>,
    hasher: &web::Data<Arc<dyn Hasher>>
) -> Result<shared::dao_models::AuthUser, HttpResponse> {
    let value = req
        .headers()
        .get(http::header::AUTHORIZATION)
        .ok_or_else(|| unauthorized_error("Missing authorization header"))?
        .to_str()
        .map_err(|_| unauthorized_error("Invalid authorization header"))?
        .to_owned();

    if value.len() < 7 {
        return Err(unauthorized_error("Invalid authorization header"));
    }

    let (token_type, token) = value.split_at(6);

    if !"Basic ".eq_ignore_ascii_case(token_type) {
        return Err(unauthorized_error("Expected a Basic authorization token"));
    }

    let token = sodiumoxide::base64::decode(token, sodiumoxide::base64::Variant::Original)
        .map_err(|_| unauthorized_error("Invalid authorization header"))?;

    let (username, password) = std::str::from_utf8(&token)
        .map_err(|_| unauthorized_error("Invalid authorization header"))
        .and_then(|value| {
            let mut iterator = value.splitn(2, ':');
            match (iterator.next(), iterator.next()) {
                (Some(username), Some(password)) if !password.is_empty() => Ok((username, password)),
                _ => Err(unauthorized_error("Invalid authorization header"))
            }
        })?;

    match db.get_user_by_username(username).await {
        Ok(Some(user)) => match hasher.verify(&user.password_hash, &password).await {
            Ok(true) => Ok(user),
            Ok(false) => Err(unauthorized_error("Incorrect username or password")),
            other => {
                log::error!("Failed to check password due to {:?}", other);
                Err(single_error(500, "Internal server error"))
            }
        },
        Ok(None) => Err(unauthorized_error("Incorrect username or password")),
        Err(error) => {
            log::error!("Failed to get user from database due to {}", error);
            Err(single_error(500, "Internal server error"))
        }
    }
}


pub async fn resolve_flags(
    req: &HttpRequest,
    db: &web::Data<Arc<dyn Database>>,
    hasher: &web::Data<Arc<dyn Hasher>>,
    flags: i64
) -> Result<shared::dao_models::AuthUser, HttpResponse> {
    let user = resolve_user(req, db, hasher).await?;

    // Wanted flag(s) or ADMIN
    if user.flags & flags == flags || user.flags & 1 << 1 == 1 << 1 {
        Ok(user)
    } else {
        Err(single_error(403, "You cannot perform this action"))
    }
}
