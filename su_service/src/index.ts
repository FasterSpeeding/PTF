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
    event.respondWith(handleRequest(event.request));
});

function wasSuccessful(response: Response): boolean {
    const contentType = response.headers.get(CONTENT_TYPE_KEY) || "";
    return (
        response.status >= 200 &&
        response.status < 300 &&
        contentType === JSON_TYPE
    );
}

function toMutableResponse(response: Response): Response {
    const headers = new Headers(response.headers);
    return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: headers,
    });
}

async function post(
    endpoint: string,
    auth: string,
    bodyInfo: { body: BodyT; contentType: string } = {
        body: "{}",
        contentType: JSON_TYPE,
    }
): Promise<Response> {
    const options = {
        body: bodyInfo.body,
        method: "post",
        headers: {
            [AUTHORIZATION_KEY]: auth,
            [CONTENT_TYPE_KEY]: bodyInfo.contentType,
        },
    };
    return await fetch(new Request(endpoint, options));
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
    let messageResponse = await post(
        `${process.env.MESSAGE_SERVICE_HOSTNAME}/messages`,
        auth
    );
    if (!wasSuccessful(messageResponse)) {
        messageResponse = toMutableResponse(messageResponse);
        messageResponse.headers.set("Forwarded", "by=message_service");
        return messageResponse;
    }

    const messageId: string = (await messageResponse.json()).id;

    // Create link
    let linkResponse = await post(
        `${process.env.AUTH_SERVICE_HOSTNAME}/messages/${messageId}/links`,
        auth
    );
    if (!wasSuccessful(linkResponse)) {
        linkResponse = toMutableResponse(linkResponse);
        linkResponse.headers.set("Forwarded", "by=auth_service");
        return linkResponse;
    }

    const linkToken: string = (await linkResponse.json()).token;

    // Create file
    let fileResponse = await fetch(
        new Request(
            `${process.env.FILE_SERVICE_HOSTNAME}/messages/${messageId}/files/${name}`,
            {
                body: data,
                headers: {
                    [AUTHORIZATION_KEY]: auth,
                    [CONTENT_TYPE_KEY]: contentType,
                },
                method: "put",
            }
        )
    );

    if (!wasSuccessful(fileResponse)) {
        fileResponse = toMutableResponse(fileResponse);
        fileResponse.headers.set("Forwarded", "by=file_service");
        return fileResponse;
    }

    const responseData = await fileResponse.json();
    const location: string = responseData.shareable_link;
    const headers = new Headers(fileResponse.headers);
    headers.set("Location", location.replace("{link_token}", linkToken));
    headers.set("Forwarded", "by=file_service");

    return new Response(JSON.stringify(responseData), {
        status: fileResponse.status,
        statusText: fileResponse.statusText,
        headers: headers,
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

    const expireAfter = url.searchParams.get("file_name");
    return await createFile(
        fileName,
        request.body,
        auth,
        contentType,
        expireAfter
    );
}
