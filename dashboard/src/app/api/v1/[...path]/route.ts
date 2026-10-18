import { NextRequest, NextResponse } from "next/server";


export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  return handleProxy(request, path);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  return handleProxy(request, path);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  return handleProxy(request, path);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  return handleProxy(request, path);
}

async function handleProxy(request: NextRequest, pathSegments: string[]) {
  // Dynamically resolve target backend at runtime (Cloud Run container env or local dev)
  const backendBase = (process.env.BACKEND_URL || "http://localhost:8000").replace(/\/+$/, "");
  const path = (pathSegments || []).join("/");
  const search = request.nextUrl.search;
  const targetUrl = `${backendBase}/api/v1/${path}${search}`;

  const headers = new Headers(request.headers);
  headers.delete("host");

  try {
    const res = await fetch(targetUrl, {
      method: request.method,
      headers: headers,
      body:
        request.method !== "GET" && request.method !== "HEAD"
          ? await request.arrayBuffer()
          : undefined,
      redirect: "manual", // Preserve 307 redirects for GCS signed video streaming
    });

    // Forward 307 redirects directly to browser for CDN streaming
    if (res.status >= 300 && res.status < 400 && res.headers.get("location")) {
      return NextResponse.redirect(new URL(res.headers.get("location")!), res.status);
    }

    const responseHeaders = new Headers(res.headers);
    responseHeaders.delete("content-encoding");

    return new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: responseHeaders,
    });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    console.error(`[API Proxy] Error forwarding to ${targetUrl}:`, errorMsg);
    // The browser gets a plain reason; the target URL and Node error stay in the server log.
    return NextResponse.json(
      { detail: "The backend is not reachable." },
      { status: 502 }
    );
  }
}
