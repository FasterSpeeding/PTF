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
use actix_web::{http, HttpRequest, HttpResponse};
use async_trait::async_trait;

use crate::utility;

pub enum AuthError {
    Error,
    Response {
        body:         Box<[u8]>,
        content_type: Option<Box<str>>,
        status_code:  u16
    }
}

impl AuthError {
    pub fn response(body: &[u8], content_type: Option<&str>, status_code: u16) -> Self {
        Self::Response {
            body: Box::from(body),
            content_type: content_type.map(Box::from),
            status_code
        }
    }
}


#[async_trait]
pub trait Auth: Send + Sync {
    async fn resolve_user(&self, authorization: &str) -> Result<shared::dto_models::User, AuthError>;
}


#[derive(Clone, Debug)]
pub struct AuthClient {
    base_url: Box<str>,
    client:   reqwest::Client
}


impl AuthClient {
    pub fn new(base_url: &str) -> Self {
        Self {
            base_url: Box::from(base_url),
            client:   reqwest::Client::new()
        }
    }
}


#[async_trait]
impl Auth for AuthClient {
    async fn resolve_user(&self, authorization: &str) -> Result<shared::dto_models::User, AuthError> {
        let response = self
            .client
            .get(self.base_url.to_string() + "/users/@me")
            .header("Authorization", authorization)
            .send()
            .await
            .map_err(|e| {
                log::error!("Auth request failed due to {:?}", e);
                AuthError::Error
            })?; // TODO: will service unavailable ever be applicable?

        if response.status().is_success() {
            response.json::<shared::dto_models::User>().await.map_err(|e| {
                log::error!("Failed to parse auth response due to {:?}", e);
                AuthError::Error
            })
        } else {
            // We don't expect the header to_str to ever fail here
            let content_type = response
                .headers()
                .get(actix_web::http::header::CONTENT_TYPE)
                .map(|v| v.to_str().unwrap_or("application/json").to_owned()); // TODO: what to do here?
            let status = response.status().as_u16();
            let body = response.bytes().await.map_err(|e| {
                log::error!("Failed to parse auth response due to {:?}", e);
                AuthError::Error
            })?;
            Err(AuthError::response(&body, content_type.as_deref(), status))
        }
    }
}


pub fn get_auth_header(req: &HttpRequest) -> Result<&str, HttpResponse> {
    req.headers()
        .get(http::header::AUTHORIZATION)
        .ok_or_else(|| utility::single_error(401, "Missing authorization header"))?
        .to_str()
        .map_err(|_| utility::single_error(400, "Invalid authorization header"))
}


pub fn map_auth_response(error: AuthError) -> HttpResponse {
    match error {
        AuthError::Error => utility::single_error(500, "Internal server error"),
        AuthError::Response {
            body,
            content_type,
            status_code
        } => {
            let mut response = HttpResponse::build(actix_web::http::StatusCode::from_u16(status_code).unwrap());

            if let Some(content_type) = content_type.as_deref() {
                response.insert_header((actix_web::http::header::CONTENT_TYPE, content_type));
            }

            if status_code == 401 {
                // TODO: auth service should decide this and we should just relay it
                response.insert_header((actix_web::http::header::WWW_AUTHENTICATE, "Basic"));
            };

            response.body(actix_web::body::Body::from_slice(&body))
        }
    }
}
