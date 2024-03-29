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
use async_trait::async_trait;
use dto_models::{Error, ErrorsResponse};

use crate::dto_models;

#[derive(Debug)]
pub enum RestError {
    Error,
    Response {
        authenticate: Option<Box<str>>,
        body:         Box<[u8]>,
        content_type: Option<Box<str>>,
        status_code:  u16
    }
}

pub type RestResult<T> = Result<T, RestError>;

impl RestError {
    pub fn response(body: &[u8], content_type: Option<&str>, status_code: u16) -> Self {
        Self::Response {
            authenticate: None,
            body: Box::from(body),
            content_type: content_type.map(Box::from),
            status_code
        }
    }

    pub fn internal_server_error() -> Self {
        Self::response(b"Internal server error", Some("text/plain; charset=UTF-8"), 500)
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
    async fn create_link(&self, authorization: &str, message_id: &uuid::Uuid) -> RestResult<dto_models::MessageLink>;
    async fn resolve_link(&self, link: &str) -> RestResult<dto_models::MessageLink>;
    async fn resolve_user(&self, authorization: &str) -> RestResult<dto_models::User>;
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


async fn relay_error(response: reqwest::Response, auth_header: Option<&str>) -> RestError {
    let content_type = response
        .headers()
        .get("Content-Type")
        .map(|value| String::from_utf8_lossy(value.as_bytes()).into_owned());

    let status = response.status().as_u16();

    match response.bytes().await {
        Ok(body) => {
            let response = RestError::response(&body, content_type.as_deref(), status);
            match auth_header {
                Some(value) => response.authenticate(value),
                None => response
            }
        }
        Err(error) => {
            log::error!("Failed to parse user auth response due to {:?}", error);
            RestError::Error
        }
    }
}


#[async_trait]
impl Auth for AuthClient {
    async fn create_link(&self, authorization: &str, message_id: &uuid::Uuid) -> RestResult<dto_models::MessageLink> {
        let response = self
            .client
            .post(format!("{}/messages/{}/links", self.base_url, message_id))
            .json(&serde_json::json!({}))
            .header("Authorization", authorization)
            .send()
            .await
            .map_err(|error| {
                log::error!("Failed to create message link due to {:?}", error);
                RestError::Error
            })?;

        if response.status().is_success() {
            response.json::<dto_models::MessageLink>().await.map_err(|error| {
                log::error!("Failed to parse message link response due to {:?}", error);
                RestError::Error
            })
        } else {
            log::error!("Failed to create message link due to receiving {:?}", response.status());
            Err(RestError::internal_server_error())
            // TODO: how are we handling content type and charset elsewhere lol?
        }
    }

    async fn resolve_user(&self, authorization: &str) -> RestResult<dto_models::User> {
        let response = self
            .client
            .get(self.base_url.to_string() + "/users/@me")
            .header("Authorization", authorization)
            .send()
            .await
            .map_err(|error| {
                log::error!("User auth request failed due to {:?}", error);
                RestError::Error
            })?; // TODO: will service unavailable ever be applicable?

        if response.status().is_success() {
            response.json::<dto_models::User>().await.map_err(|error| {
                log::error!("Failed to parse user auth response due to {:?}", error);
                RestError::Error
            })
        } else {
            Err(relay_error(response, Some("Basic")).await)
        }
    }

    async fn resolve_link(&self, link: &str) -> RestResult<dto_models::MessageLink> {
        let response = self
            .client
            .get(format!("{}/links/{}", self.base_url, link))
            .send()
            .await
            .map_err(|error| {
                log::error!("Auth request failed due to {:?}", error);
                RestError::Error
            })?;

        match response.status() {
            reqwest::StatusCode::OK => response.json::<dto_models::MessageLink>().await.map_err(|e| {
                log::error!("Failed to parse link auth response due to {:?}", e);
                RestError::Error
            }),
            reqwest::StatusCode::NOT_FOUND => {
                let response =
                    ErrorsResponse::default().with_error(Error::default().status(401).detail("Message link not found"));
                Err(RestError::response(
                    serde_json::to_string(&response).unwrap().as_bytes(),
                    Some("application/json"),
                    403
                ))
            }
            _ => Err(relay_error(response, None).await)
        }
    }
}
