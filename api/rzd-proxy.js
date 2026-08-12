export const config = { runtime: "edge" };

export default async function handler(request) {
  if (request.method !== "GET" || request.headers.get("x-rzd-relay") !== "train-pricing") {
    return new Response(JSON.stringify({ error: "Not found" }), {
      status: 404,
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  }

  const incoming = new URL(request.url);
  const target = new URL(
    "https://ticket.rzd.ru/api/v1/railway-service/prices/train-pricing",
  );
  target.search = incoming.search;

  const response = await fetch(target, {
    headers: {
      accept: "application/json, text/plain, */*",
      referer: "https://ticket.rzd.ru/",
      "user-agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36",
    },
  });
  return new Response(response.body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
