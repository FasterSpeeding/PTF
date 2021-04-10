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
pub mod dao_models;
pub mod dto_models;
pub mod sql;

#[cfg(feature = "postgres")]
pub mod postgres;


#[derive(Debug)]
pub struct MissingEnvVariable<'a> {
    pub key: &'a str
}

impl std::error::Error for MissingEnvVariable<'_> {
}

impl std::fmt::Display for MissingEnvVariable<'_> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Couldnt load missing env variable {}", self.key)
    }
}


pub fn get_env_variable(key: &str) -> Result<String, MissingEnvVariable<'_>> {
    dotenv::var(key)
        .or_else(|_| std::env::var(key))
        .map_err(|_| MissingEnvVariable { key })
}

pub fn setup_logging() {
    let level = get_env_variable("LOG_LEVEL").unwrap_or_else(|_| "INFO".to_owned());
    let level = match level.to_uppercase().as_str() {
        "TRACE" => log::LevelFilter::Trace,
        "DEBUG" => log::LevelFilter::Debug,
        "INFO" => log::LevelFilter::Info,
        "WARN" => log::LevelFilter::Warn,
        "ERROR" => log::LevelFilter::Error,
        other => panic!(
            "Invalid log level provided, expected TRACE, DEBUG, INFO, WARN or ERROR but found '{}'",
            other
        )
    };

    simple_logger::SimpleLogger::new().with_level(level).init().unwrap();
}


pub fn remove_protocol(url: String) -> String {
    let mut result: Vec<String> = url.splitn(2, "//").map(str::to_owned).collect();
    if result.len() > 1 {
        result.remove(1)
    } else {
        result.remove(0)
    }
}
