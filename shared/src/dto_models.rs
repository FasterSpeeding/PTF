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
use lazy_static::lazy_static;
use serde::{de, Deserialize, Serialize};
use validator::Validate;


const RAW_USERNAME_REGEX: &str = r"^[\w\-\s]+$";
const MINIMUM_NAME_LENGTH: usize = 3;
const MAXIMUM_NAME_LENGTH: usize = 32;

const MINIMUM_PASSWORD_LENGTH: usize = 8;
const MAXIMUM_PASSWORD_LENGTH: usize = 120;

lazy_static! {
    static ref USERNAME_REGEX: regex::Regex = regex::Regex::new(RAW_USERNAME_REGEX).unwrap();
}

struct DurationVisitor;

impl<'de> de::Visitor<'de> for DurationVisitor {
    type Value = chrono::Duration;

    fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(formatter, "an iso8601 duration string")
    }

    fn visit_str<Error>(self, value: &str) -> Result<Self::Value, Error>
    where
        Error: de::Error {
        time_parse::duration::parse(value)
            .map(chrono::Duration::from_std)
            .map_err(|error| Error::custom(format!("invalid duration: {}", error)))?
            .map_err(|error| Error::custom(format!("invalid duration: {}", error)))
    }
}

struct OptionalDurationVisitor;

impl<'de> de::Visitor<'de> for OptionalDurationVisitor {
    type Value = Option<chrono::Duration>;

    fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(formatter, "null or an iso8601 duration string")
    }

    fn visit_none<Error>(self) -> Result<Self::Value, Error>
    where
        Error: de::Error {
        Ok(None)
    }

    fn visit_some<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
    where
        D: de::Deserializer<'de> {
        deserializer.deserialize_any(DurationVisitor).map(Some)
    }
}

pub fn deserialize_optional_duration<'de, D>(deserializer: D) -> Result<Option<chrono::Duration>, D::Error>
where
    D: serde::Deserializer<'de> {
    deserializer.deserialize_option(OptionalDurationVisitor)
}

pub fn deserialize_duration<'de, D>(deserializer: D) -> Result<chrono::Duration, D::Error>
where
    D: serde::Deserializer<'de> {
    deserializer.deserialize_any(DurationVisitor)
}

pub fn serialize_duration(duration: chrono::Duration) -> String {
    // TODO: be smarter here to avoid encouraging C code to buffer overflow
    format!("PT{}S", duration.num_seconds())  // This is ISO8601
}


#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct File {
    pub content_type:   String,
    pub file_name:      String,
    pub message_id:     uuid::Uuid,
    pub private_link:   String,
    pub shareable_link: String,
    pub set_at:         chrono::DateTime<chrono::Utc>
}

impl File {
    pub fn from_dao(model: crate::dao_models::File, base_url: &str) -> Self {
        let file_name = urlencoding::encode(&model.file_name);
        let private_link = format!("{}/messages/{}/files/{}", base_url, &model.message_id, &file_name);
        let shareable_link = format!("{}/shared", &private_link);
        Self {
            content_type: model.content_type,
            file_name: model.file_name,
            message_id: model.message_id,
            private_link,
            shareable_link,
            set_at: model.set_at
        }
    }
}


#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Message {
    pub id:             uuid::Uuid,
    pub created_at:     chrono::DateTime<chrono::Utc>,
    pub expires_at:     Option<chrono::DateTime<chrono::Utc>>,
    pub is_transient:   bool,
    pub private_link:   String,
    pub shareable_link: String,
    pub text:           Option<String>,
    pub title:          Option<String>,
    pub files:          Vec<File>,
}



#[derive(Clone, Debug, Deserialize, Serialize, sqlx::FromRow)]
pub struct User {
    pub id:         uuid::Uuid,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub flags:      i64, // TODO: flags?
    pub username:   String
}

// TODO: find a better (possibly automatic) way to handle this
impl User {
    pub fn from_auth(user: crate::dao_models::AuthUser) -> Self {
        Self {
            id:         user.id,
            created_at: user.created_at,
            flags:      user.flags,
            username:   user.username
        }
    }
}


#[derive(Clone, Debug, Deserialize, Validate)]
pub struct ReceivedUser {
    #[validate(range(min = 0))]
    pub flags:    i64, // TODO: flags?
    #[validate(length(min = "MINIMUM_PASSWORD_LENGTH", max = "MAXIMUM_PASSWORD_LENGTH"))]
    pub password: String,
    #[validate(length(min = "MINIMUM_NAME_LENGTH", max = "MAXIMUM_NAME_LENGTH"))]
    #[validate(regex = "USERNAME_REGEX")]
    pub username: String
}


#[derive(Clone, Debug, Deserialize, Validate)]
pub struct UserUpdate {
    #[validate(range(min = 0))]
    pub flags:    Option<i64>,
    #[validate(length(min = "MINIMUM_PASSWORD_LENGTH", max = "MAXIMUM_PASSWORD_LENGTH"))]
    pub password: Option<String>,
    #[validate(length(min = "MINIMUM_NAME_LENGTH", max = "MAXIMUM_NAME_LENGTH"))]
    #[validate(regex = "USERNAME_REGEX")]
    pub username: Option<String>
}


#[derive(Deserialize, Serialize)]
pub struct LinkQuery {
    pub link: String
}


fn zero_default() -> i16 {
    0
}


#[derive(Clone, Debug, Deserialize, sqlx::FromRow)]
pub struct ReceivedMessageLink {
    #[serde(default = "zero_default")]
    pub access:        i16,
    #[serde(default, deserialize_with = "deserialize_optional_duration")]
    pub expire_after:  Option<chrono::Duration>,
    pub resource:      Option<String>
}


#[derive(std::default::Default, Serialize)]
pub struct ErrorsResponse {
    pub errors: Vec<Error>
}


impl ErrorsResponse {
    pub fn with_error(mut self, error: Error) -> Self {
        self.errors.push(error);
        self
    }
}

#[derive(std::default::Default, Serialize)]
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
        self.source = Some(Source {
            pointer:   None,
            parameter: Some(Box::from(source))
        });
        self
    }

    pub fn pointer(mut self, source: &str) -> Self {
        self.source = Some(Source {
            pointer:   Some(Box::from(source)),
            parameter: None
        });
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

    pub fn from_validation_errors(errors: &validator::ValidationErrors) -> Self {
        let result = Self::default();

        // errors.errors().iter().
        // TODO: implement this

        result
    }
}

fn path_validator_errors(error: &validator::ValidationErrorsKind) {
    // TODO: implement this
    match error {
        validator::ValidationErrorsKind::Struct(errors) => {}
        validator::ValidationErrorsKind::List(errors) => {}
        validator::ValidationErrorsKind::Field(errors) => {}
    }
}


#[derive(Serialize)]
pub struct Source {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pointer:   Option<Box<str>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parameter: Option<Box<str>>
}
