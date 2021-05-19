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
use std::error::Error;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use async_trait::async_trait;


#[async_trait]
pub trait FileReader: Send + Sync {
    async fn delete_file(&self, file: &shared::dao_models::File) -> Result<(), Box<dyn Error>>;
    async fn read_file(&self, file: &shared::dao_models::File) -> Result<Vec<u8>, Box<dyn Error>>;
    async fn save_file(
        &self,
        message_id: &uuid::Uuid,
        set_at: &chrono::DateTime<chrono::Utc>,
        file_name: &str,
        data: &[u8]
    ) -> Result<(), Box<dyn Error>>;
}

#[derive(Clone, Debug)]
pub struct LocalReader {
    base_url: Arc<Path>
}


impl LocalReader {
    pub fn new(base_url: &str) -> Self {
        Self {
            base_url: Arc::from(Path::new(base_url))
        }
    }

    fn build_url(&self, message_id: &uuid::Uuid, created_at: &chrono::DateTime<chrono::Utc>) -> PathBuf {
        let mut path = self.base_url.to_path_buf();
        path.push(format!("{}#{}", message_id, created_at.timestamp_millis()));
        path
    }
}


#[async_trait]
impl FileReader for LocalReader {
    async fn delete_file(&self, file: &shared::dao_models::File) -> Result<(), Box<dyn Error>> {
        tokio::fs::remove_file(self.build_url(&file.message_id, &file.set_at))
            .await
            .map_err(Box::from)
    }

    async fn read_file(&self, file: &shared::dao_models::File) -> Result<Vec<u8>, Box<dyn Error>> {
        tokio::fs::read(self.build_url(&file.message_id, &file.set_at))
            .await
            .map_err(Box::from) // TODO: lazily read and return a stream
    }

    async fn save_file(
        &self,
        message_id: &uuid::Uuid,
        set_at: &chrono::DateTime<chrono::Utc>,
        _file_name: &str,
        data: &[u8]
    ) -> Result<(), Box<dyn Error>> {
        tokio::fs::write(self.build_url(message_id, set_at), data)
            .await
            .map_err(Box::from) // TODO: take a stream and lazily save
    }
}
