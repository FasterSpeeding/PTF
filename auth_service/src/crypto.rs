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
use core::convert::AsRef;
use std::error::Error;

use async_trait::async_trait;
use sodiumoxide::crypto::pwhash::argon2id13;


#[async_trait]
pub trait Hasher: Send + Sync {
    async fn verify(&self, hash: &str, password: &str) -> Result<bool, Box<dyn Error>>;
    async fn hash(&self, password: &str) -> Result<String, Box<dyn Error>>;
}


#[derive(Clone, Debug)]
pub struct HashError {
    pub message: String
}

impl HashError {
    pub fn new(message: &str) -> Self {
        Self::from_string(message.to_owned())
    }

    pub fn from_string(message: String) -> Self {
        Self { message }
    }
}

impl Error for HashError {
}

impl std::fmt::Display for HashError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.message)
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
        let mut hash = hash.as_bytes().to_owned();
        hash.resize(argon2id13::HASHEDPASSWORDBYTES, 0);

        let hash =
            argon2id13::HashedPassword::from_slice(&hash).ok_or_else(|| HashError::new("Invalid stored hash"))?;
        let password = password.to_owned();
        tokio::task::spawn_blocking(move || argon2id13::pwhash_verify(&hash, password.as_bytes()))
            .await
            .map_err(Box::from)
    }

    async fn hash(&self, password: &str) -> Result<String, Box<dyn Error>> {
        // TODO this is slightly slow
        let password = password.to_owned();
        let mut result = tokio::task::spawn_blocking(move || {
            argon2id13::pwhash(
                password.as_bytes(),
                argon2id13::OPSLIMIT_INTERACTIVE,
                argon2id13::MEMLIMIT_INTERACTIVE
            )
            .map_err(|_| Box::new(HashError::new("Failed to hash password")))
        })
        .await
        .map_err(Box::new)?
        .map(|v| v.as_ref().to_vec())?;

        while result.ends_with(&[0]) {
            // Remove padding which would otherwise lead to an error down the line.
            result.pop();
        }

        std::string::String::from_utf8(result).map_err(|e| {
            Box::new(HashError::from_string(format!("Failed to parse password due to {}", e))) as Box<dyn Error>
        })
    }
}
