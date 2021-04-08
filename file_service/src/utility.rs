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
use actix_web::{http, HttpResponse};
use shared::dto_models;
use shared::sql::DatabaseResult;

pub fn single_error(status: u16, detail: &str) -> HttpResponse {
    let data =
        dto_models::ErrorsResponse::default().with_error(dto_models::Error::default().status(status).detail(detail));

    let mut response = HttpResponse::build(http::StatusCode::from_u16(status).unwrap());

    if status == 401 {
        response.insert_header((actix_web::http::header::WWW_AUTHENTICATE, "Basic"));
    };

    response.json(data)
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