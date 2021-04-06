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
use std::error::Error;

use async_trait::async_trait;


#[async_trait]
pub trait Hasher: Sync {
    async fn verify(&self, hash: &str, password: &str) -> Result<bool, Box<dyn Error>>;
    async fn hash(&self, password: &str) -> Result<String, Box<dyn Error>>;
}


#[derive(Clone, Debug)]
pub struct ArgonError {
    pub inner_error: argonautica::Error
}

impl Error for ArgonError {
}

impl std::fmt::Display for ArgonError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        self.inner_error.fmt(f)
    }
}

#[derive(Clone, Debug)]
pub struct Argon;


impl Argon {
    pub fn new() -> Self {
        Self {}
    }
}


#[async_trait]
impl Hasher for Argon {
    async fn verify(&self, hash: &str, password: &str) -> Result<bool, Box<dyn Error>> {
        // TODO this is really slow
        let hash = hash.to_owned();
        let password = password.to_owned();
        let result = tokio::task::spawn_blocking(move || {
            argonautica::Verifier::default()
                .with_hash(&hash)
                .with_password(password)
                .verify() // TOOD: verify_non_blocking
        })
        .await;

        match result {
            Ok(Ok(value)) => Ok(value),
            Ok(Err(error)) => Err(Box::from(ArgonError { inner_error: error })),
            Err(error) => Err(Box::from(error))
        }
    }

    async fn hash(&self, password: &str) -> Result<String, Box<dyn Error>> {
        // TODO this is really slow
        let password = password.to_owned();
        let result = tokio::task::spawn_blocking(move || {
            argonautica::Hasher::default()
                .with_password(password)
                .opt_out_of_secret_key(true)
                .configure_variant(argonautica::config::Variant::Argon2id)
                .hash() // TODO: hash_non_blocking
        })
        .await;

        match result {
            Ok(Ok(value)) => Ok(value),
            Ok(Err(error)) => Err(Box::from(ArgonError { inner_error: error })),
            Err(error) => Err(Box::from(error))
        }
    }
}
