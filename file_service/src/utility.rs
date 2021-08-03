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
use actix_web::{http, HttpRequest, HttpResponse};
use shared::sql::DatabaseResult;
use shared::{clients, dto_models};

pub fn single_error(status: u16, detail: &str) -> actix_web::error::InternalError<&str> {
    let data =
        dto_models::ErrorsResponse::default().with_error(dto_models::Error::default().status(status).detail(detail));

    let mut response = HttpResponse::build(http::StatusCode::from_u16(status).unwrap());

    if status == 401 {
        response.insert_header((http::header::WWW_AUTHENTICATE, "Basic"));
    };

    actix_web::error::InternalError::from_response(detail, response.json(data))
}


pub fn get_auth_header(req: &HttpRequest) -> Result<&str, actix_web::error::InternalError<&'static str>> {
    match req.headers().get(http::header::AUTHORIZATION).map(|v| v.to_str()) {
        Some(Ok(value)) => Ok(value),
        Some(Err(_)) => Err(single_error(401, "Invalid authorization header")),
        None => Err(single_error(401, "Missing authorization header"))
    }
}


pub fn resolve_database_entry<T>(
    result: DatabaseResult<T>,
    resource_name: &str
) -> Result<T, actix_web::error::InternalError<&'static str>> {
    match result {
        Ok(Some(entry)) => Ok(entry),
        Ok(None) => Err(single_error(404, "Resource not found")), // TODO: include name in error msg
        Err(error) => {
            log::error!("Failed to get entry from SQL database due to {}", error);

            // TODO: will service unavailable ever be applicable?
            Err(single_error(500, "Database lookup failed"))
        }
    }
}

pub fn map_auth_response(error: clients::RestError) -> actix_web::error::InternalError<&'static str> {
    match error {
        clients::RestError::Error => single_error(500, "Internal server error"),
        clients::RestError::Response {
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

            // TODO: is that detail ok?
            actix_web::error::InternalError::from_response(
                "Failed to authorize",
                response.body(actix_web::body::Body::from_slice(&body))
            )
        }
    }
}
