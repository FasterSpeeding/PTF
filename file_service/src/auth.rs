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
use dto_models::{Error, ErrorsResponse};
use shared::{dao_models, dto_models};

use crate::utility;

#[derive(Debug)]
pub enum AuthError {
    Error,
    Response {
        authenticate: Option<Box<str>>,
        body:         Box<[u8]>,
        content_type: Option<Box<str>>,
        status_code:  u16
    }
}

impl AuthError {
    pub fn response(body: &[u8], content_type: Option<&str>, status_code: u16) -> Self {
        Self::Response {
            authenticate: None,
            body: Box::from(body),
            content_type: content_type.map(Box::from),
            status_code
        }
    }

    pub fn authenticate(self, value: &str) -> Self {
        match self {
            Self::Response {
                body,
                content_type,
                status_code,
                ..
            } => Self::Response {
                authenticate: Some(Box::from(value)),
                body,
                content_type,
                status_code
            },
            other => panic!("Cannot set authenticate on {:?} error type", other)
        }
    }
}


#[async_trait]
pub trait Auth: Send + Sync {
    async fn resolve_link(&self, message_id: &uuid::Uuid, link: &str) -> Result<dao_models::MessageLink, AuthError>;
    async fn resolve_user(&self, authorization: &str) -> Result<dto_models::User, AuthError>;
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


async fn relay_error(response: reqwest::Response, auth_header: Option<&str>) -> AuthError {
    // We don't expect the header to_str to ever fail here
    let content_type = response
        .headers()
        .get(http::header::CONTENT_TYPE)
        .map(|v| v.to_str().unwrap_or("application/json").to_owned()); // TODO: what to do here?
    let status = response.status().as_u16();

    match response.bytes().await {
        Ok(body) => {
            let response = AuthError::response(&body, content_type.as_deref(), status);
            match auth_header {
                Some(value) => response.authenticate(value),
                None => response
            }
        }
        Err(error) => {
            log::error!("Failed to parse user auth response due to {:?}", error);
            AuthError::Error
        }
    }
}


#[async_trait]
impl Auth for AuthClient {
    async fn resolve_user(&self, authorization: &str) -> Result<dto_models::User, AuthError> {
        let response = self
            .client
            .get(self.base_url.to_string() + "/users/@me")
            .header("Authorization", authorization)
            .send()
            .await
            .map_err(|e| {
                log::error!("User auth request failed due to {:?}", e);
                AuthError::Error
            })?; // TODO: will service unavailable ever be applicable?

        if response.status().is_success() {
            response.json::<dto_models::User>().await.map_err(|e| {
                log::error!("Failed to parse user auth response due to {:?}", e);
                AuthError::Error
            })
        } else {
            Err(relay_error(response, Some("Basic")).await)
        }
    }

    async fn resolve_link(&self, message_id: &uuid::Uuid, link: &str) -> Result<dao_models::MessageLink, AuthError> {
        let response = self
            .client
            .get(format!("{}/messages/{}/links/{}", self.base_url, message_id, link))
            .send()
            .await
            .map_err(|e| {
                log::error!("Auth request failed due to {:?}", e);
                AuthError::Error
            })?;

        match response.status() {
            reqwest::StatusCode::OK => response.json::<dao_models::MessageLink>().await.map_err(|e| {
                log::error!("Failed to parse link auth response due to {:?}", e);
                AuthError::Error
            }),
            reqwest::StatusCode::NOT_FOUND => {
                let response =
                    ErrorsResponse::default().with_error(Error::default().status(401).detail("Message link not found"));
                Err(AuthError::response(
                    serde_json::to_string(&response).unwrap().as_bytes(),
                    Some("application/json"),
                    401
                ))
            }
            _ => Err(relay_error(response, None).await)
        }
    }
}


pub fn get_auth_header(req: &HttpRequest) -> Result<&str, HttpResponse> {
    let result = match req.headers().get(http::header::AUTHORIZATION).map(|v| v.to_str()) {
        Some(Ok(value)) => Ok(value),
        Some(Err(_)) => Err("Invalid authorization header"),
        None => Err("Missing authorization header")
    };

    result.map_err(|message| {
        let response = ErrorsResponse::default().with_error(Error::default().status(401).detail(message));
        HttpResponse::Unauthorized()
            .insert_header((http::header::WWW_AUTHENTICATE, "Basic"))
            .json(response)
    })
}

pub fn map_auth_response(error: AuthError) -> HttpResponse {
    match error {
        AuthError::Error => utility::single_error(500, "Internal server error"),
        AuthError::Response {
            authenticate,
            body,
            content_type,
            status_code
        } => {
            let mut response = HttpResponse::build(http::StatusCode::from_u16(status_code).unwrap());

            if let Some(authenticate) = authenticate.as_deref() {
                response.insert_header((http::header::WWW_AUTHENTICATE, authenticate));
            }

            if let Some(content_type) = content_type.as_deref() {
                response.insert_header((http::header::CONTENT_TYPE, content_type));
            }

            response.body(actix_web::body::Body::from_slice(&body))
        }
    }
}
