# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2021, Faster Speeding
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
from __future__ import annotations

import pathlib
import secrets
import time
import typing

from OpenSSL import crypto

CERTIFICATE_EXPIRE: typing.Final[int] = 631152000  # 20 years in seconds


def create_ca(base_path: typing.Optional[pathlib.Path]) -> typing.Tuple[crypto.PKey, crypto.X509]:
    ca_key = crypto.PKey()
    ca_key.generate_key(crypto.TYPE_RSA, 2048)

    ca_cert = crypto.X509()
    ca_cert.set_version(2)
    ca_cert.get_subject().CN = f"PTF {time.time()}"
    ca_cert.set_serial_number(secrets.randbits(64))

    ca_cert.add_extensions([crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=ca_cert)])
    ca_cert.add_extensions(
        [
            crypto.X509Extension(b"authorityKeyIdentifier", False, b"keyid:always", issuer=ca_cert),
            crypto.X509Extension(b"basicConstraints", False, b"CA:TRUE"),
            crypto.X509Extension(b"keyUsage", False, b"keyCertSign, cRLSign"),
        ]
    )

    ca_cert.gmtime_adj_notBefore(0)
    ca_cert.gmtime_adj_notAfter(CERTIFICATE_EXPIRE)

    ca_cert.set_issuer(ca_cert.get_subject())
    ca_cert.set_pubkey(ca_key)
    ca_cert.sign(ca_key, "sha256")

    if base_path:
        base_path.mkdir(parents=True, exist_ok=True)

        with (base_path / "ca.key").open("w+b") as file:
            file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, ca_key))

        with (base_path / "ca.crt").open("w+b") as file:
            file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert))

    return ca_key, ca_cert


def create_client_cert(
    base_path: typing.Optional[pathlib.Path], client_name: str, ca_key: crypto.PKey, ca_cert: crypto.X509
) -> typing.Tuple[crypto.PKey, crypto.X509]:
    client_key = crypto.PKey()
    client_key.generate_key(crypto.TYPE_RSA, 2048)

    client_cert = crypto.X509()
    client_cert.set_version(2)
    client_cert.set_serial_number(secrets.randbits(64))

    client_cert.get_subject().commonName = f"{client_name} {time.time()}"

    client_cert.add_extensions(
        [
            crypto.X509Extension(b"basicConstraints", False, b"CA:FALSE"),
            crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=client_cert),
            crypto.X509Extension(b"authorityKeyIdentifier", False, b"keyid:always", issuer=ca_cert),
            crypto.X509Extension(b"extendedKeyUsage", False, b"clientAuth"),
            crypto.X509Extension(b"keyUsage", False, b"digitalSignature"),
        ]
    )

    client_cert.set_issuer(ca_cert.get_subject())
    client_cert.set_pubkey(client_key)
    client_cert.gmtime_adj_notBefore(0)
    client_cert.gmtime_adj_notAfter(CERTIFICATE_EXPIRE)
    client_cert.sign(ca_key, "sha256")

    if base_path:
        base_path.mkdir(parents=True, exist_ok=True)

        client_name = client_name.lower().replace(" ", "_")
        with (base_path / f"{client_name}.key").open("w+b") as file:
            file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, client_key))

        with (base_path / f"{client_name}.crt").open("w+b") as file:
            file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, client_cert))

    return client_key, client_cert


if __name__ == "__main__":
    _base_path = pathlib.Path("./.ssl/")
    _ca_key, _ca_cert = create_ca(_base_path)

    for _service in ("Auth Service", "File Service", "REST Service"):
        create_client_cert(_base_path, _service, _ca_key, _ca_cert)
