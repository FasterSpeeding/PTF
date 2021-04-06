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

#[async_trait]
pub trait Auth: Send {
    async fn resolve_user(&self, authorization: &str) -> Result<shared::dto_models::User, Box<dyn std::error::Error>>;
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
    async fn resolve_user(&self, authorization: &str) -> Result<shared::dto_models::User, Box<dyn std::error::Error>> {
        self.client
            .get(self.base_url.to_string() + "/users/@me")
            .header("Authorization", authorization)
            .send()
            .await?
            .json::<shared::dto_models::User>()
            .await
            .map_err(Box::from)
    }
}


pub fn get_auth_header(req: &HttpRequest) -> Result<&str, HttpResponse> {
    req.headers()
        .get(http::header::AUTHORIZATION)
        .ok_or_else(|| utility::single_error(401, "Missing authorization header"))?
        .to_str()
        .map_err(|_| utility::single_error(400, "Invalid authorization header"))
}
