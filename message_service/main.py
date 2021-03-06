# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2021, Lucina
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from src import utilities


# Uvicorn, hypercorn, daphne, Gunicorn
def run_uvicorn(metadata: utilities.Metadata) -> None:
    import uvicorn  # type: ignore[import]

    uvicorn.run(
        "src.builder:build",
        factory=True,
        host=metadata.address,
        port=metadata.port,
        log_level=metadata.log_level,
        ssl_keyfile=metadata.ssl_key,
        ssl_certfile=metadata.ssl_cert,
    )


def run_hypercorn(metadata: utilities.Metadata) -> None:
    import hypercorn.run

    config = hypercorn.Config()
    config.application_path = "src.app:app"
    config.bind = [f"{metadata.address}:{metadata.port}"]
    config.worker_class = "asyncio"
    config.loglevel = metadata.log_level
    config.certfile = metadata.ssl_cert
    config.keyfile = metadata.ssl_key

    hypercorn.run.run(config)


if __name__ == "__main__":
    run_uvicorn(utilities.Metadata())
    # run_hypercorn(utilities.Metadata())
