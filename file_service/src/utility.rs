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
use std::sync::Arc;

use actix_web::{http, web, HttpRequest, HttpResponse};

use crate::sql::traits::{Database, DatabaseResult};
use crate::{errors, sql};

pub fn setup_logging(level: &str) {
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


pub fn single_error(status: u16, detail: &str) -> HttpResponse {
    let response = errors::ErrorsResponse::new().with_error(errors::Error::new().status(status).detail(detail));

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

// TODO: use actix-web-httpauth here when actix-web 4.0.0 releases
pub async fn resolve_user(
    req: &HttpRequest,
    db: &web::Data<Arc<dyn Database>>
) -> Result<sql::dao_models::User, HttpResponse> {
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
        return Err(single_error(401, "Expected a Bearer token"));
    }

    let token = base64::decode(token).map_err(|_| single_error(400, "Invalid authorization header"))?;
    let (username, password) = std::str::from_utf8(&token)
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
            // TODO: this is kinda slow
            let password_hash = user.password_hash.clone();
            let password = password.to_owned();
            let result = tokio::task::spawn_blocking(move || {
                argonautica::Verifier::default()
                    .with_hash(&password_hash)
                    .with_password(password)
                    .verify()
            })
            .await
            .map_err(|e| {
                log::error!("Failed to check password due to {}", e);
                single_error(500, "Internal server error")
            })?
            .map_err(|e| {
                log::error!("Failed to check password due to {}", e);
                single_error(500, "Internal server error")
            })?;

            if result {
                Ok(user)
            } else {
                Err(single_error(401, "Incorrect username or password"))
            }
        }
        Ok(None) => Err(single_error(401, "Incorrect username or password")),
        Err(error) => {
            log::error!("Failed to get user from database due to {}", error);
            Err(single_error(400, "Internal server error"))
        }
    }
}
