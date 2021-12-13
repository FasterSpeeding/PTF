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
type BodyT = string | ReadableStream | FormData | URLSearchParams;

const AUTHORIZATION_KEY = "Authorization";
const CONTENT_TYPE_KEY = "Content-Type";
const JSON_TYPE = "application/json";

addEventListener("fetch", (event) => {
    const event_ = event as FetchEvent;
    event_.respondWith(handleRequest(event_.request));
});

async function request(
    endpoint: string,
    auth: string,
    serviceName: string,
    bodyInfo: { body: BodyT; contentType: string } = {
        body: "{}",
        contentType: JSON_TYPE,
    },
    method: string = "post"
): Promise<any> {
    const options = {
        body: bodyInfo.body,
        method: method,
        headers: {
            [AUTHORIZATION_KEY]: auth,
            [CONTENT_TYPE_KEY]: bodyInfo.contentType,
        },
    };
    let response = await fetch(new Request(endpoint, options));

    // Check for failure
    if (response.status < 200 || response.status >= 300) {
        // response.headers is read-only for received responses so we have to replace this.
        response = new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: new Headers(response.headers),
        });
        response.headers.set("Response-Source", `by=${serviceName}`);
        throw response;
    }

    return await response.json();
}

async function createFile(
    name: string,
    data: BodyT,
    auth: string,
    contentType: string,
    expireAfter: string | null = null
): Promise<Response> {
    name = encodeURIComponent(name);
    // Create a new message
    const messageResponse = await request(
        `${process.env.MESSAGE_SERVICE_HOSTNAME}/messages`,
        auth,
        "message-service"
    );

    // Create link
    const linkResponse = await request(
        `${process.env.AUTH_SERVICE_HOSTNAME}/messages/${messageResponse.id}/links`,
        auth,
        "auth-service"
    );

    // Create file
    const responseData = await request(
        `${process.env.FILE_SERVICE_HOSTNAME}/messages/${messageResponse.id}/files/${name}`,
        auth,
        "file-service",
        { body: data, contentType: contentType },
        "put"
    );

    const location: string = responseData.shareable_link;
    return new Response(JSON.stringify(responseData), {
        status: 201,
        headers: {
            [CONTENT_TYPE_KEY]: JSON_TYPE,
            Location: location.replace("{link_token}", linkResponse.token),
        },
    });
}

async function handleRequest(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const pathNames = url.pathname.split("/");
    const fileName = pathNames[pathNames.length - 1];

    // This expects /files/{file.name}
    if (pathNames.length !== 3 || !fileName) {
        return new Response(null, { status: 404 });
    }

    if (request.method !== "POST") {
        return new Response(null, { status: 405 });
    }

    const auth = request.headers.get(AUTHORIZATION_KEY);
    if (!auth) {
        return new Response("Missing authorization header", {
            status: 403,
            headers: { "WWW-Authenticate": "Basic" },
        });
    }
    const contentType = request.headers.get(CONTENT_TYPE_KEY);
    if (!contentType) {
        return new Response("Missing content type header", { status: 400 });
    }

    if (request.body === null) {
        return new Response("Missing body", { status: 400 });
    }

    try {
        return await createFile(
            fileName,
            request.body,
            auth,
            contentType,
            url.searchParams.get("file_name")
        );
    } catch (error) {
        if (error instanceof Response) {
            return error;
        }

        throw error;
    }
}
