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
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize, sqlx::FromRow)]
pub struct User {
    pub id:         i64,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub flags:      i64, // TODO: flags?
    pub username:   String
}

// TODO: find a better (possibly automatic) way to handle this
impl User {
    pub fn from_dao(user: crate::dao_models::User) -> Self {
        Self {
            id:         user.id,
            created_at: user.created_at,
            flags:      user.flags,
            username:   user.username
        }
    }
}


#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ReceivedUser {
    pub flags:    i64, // TODO: flags?
    pub password: String
}


#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct UserUpdate {
    pub flags:    Option<i64>,
    pub username: Option<String>,
    pub password: Option<String>
}


#[derive(Deserialize, Serialize)]
pub struct ErrorsResponse {
    pub errors: Vec<Error>
}

impl ErrorsResponse {
    pub fn new() -> Self {
        Self { errors: Vec::new() }
    }

    pub fn with_error(mut self, error: Error) -> Self {
        self.errors.push(error);
        self
    }
}

#[derive(Deserialize, Serialize)]
pub struct Error {
    // TODO: this is currently JSON:API error style but look at rfc2616 and rfc7807
    #[serde(skip_serializing_if = "Option::is_none")]
    code:       Option<Box<str>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<Box<str>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id:     Option<Box<str>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<Source>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title:  Option<Box<str>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub meta:   Option<std::collections::HashMap<Box<str>, Box<str>>>
}

// TODO: links?
impl Error {
    pub fn new() -> Self {
        Self {
            code:   None,
            detail: None,
            id:     None,
            source: None,
            status: None,
            title:  None,
            meta:   None
        }
    }

    pub fn code(mut self, code: &str) -> Self {
        self.code = Some(Box::from(code));
        self
    }

    pub fn detail(mut self, description: &str) -> Self {
        self.detail = Some(Box::from(description));
        self
    }

    pub fn id(mut self, id: &str) -> Self {
        self.id = Some(Box::from(id));
        self
    }

    pub fn status(mut self, status_code: u16) -> Self {
        self.status = Some(status_code);
        self
    }

    pub fn title(mut self, title: &str) -> Self {
        self.title = Some(Box::from(title));
        self
    }

    pub fn parameter(mut self, source: &str) -> Self {
        self.source = Some(Source::parameter(source));
        self
    }

    pub fn pointer(mut self, source: &str) -> Self {
        self.source = Some(Source::pointer(source));
        self
    }

    pub fn meta_field(mut self, key: &str, value: &str) -> Self {
        let key = Box::from(key);
        let value = Box::from(value);
        match &mut self.meta {
            Some(map) => {
                map.insert(key, value);
            }
            None => {
                self.meta = Some([(key, value)].iter().cloned().collect());
            }
        };
        self
    }
}

#[derive(Deserialize, Serialize)]
pub struct Source {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pointer:   Option<Box<str>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parameter: Option<Box<str>>
}

impl Source {
    fn pointer(pointer: &str) -> Self {
        Self {
            pointer:   Some(Box::from(pointer)),
            parameter: None
        }
    }

    fn parameter(parameter: &str) -> Self {
        Self {
            pointer:   None,
            parameter: Some(Box::from(parameter))
        }
    }
}
