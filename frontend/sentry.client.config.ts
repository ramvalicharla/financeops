import * as Sentry from "@sentry/nextjs";

export function scrubSentryEvent(event: Sentry.Event): Sentry.Event {
  if (event.user) {
    delete event.user.email;
    delete event.user.username;
    delete event.user.ip_address;
  }

  if (event.request?.headers) {
    const headers = event.request.headers as Record<string, unknown>;
    delete headers.authorization;
    delete headers.Authorization;
    delete headers.cookie;
    delete headers.Cookie;
    delete headers["x-api-key"];
    delete headers["X-Api-Key"];
  }

  if (event.request?.url) {
    try {
      const url = new URL(event.request.url);
      url.searchParams.delete("token");
      url.searchParams.delete("api_key");
      url.searchParams.delete("secret");
      event.request.url = url.toString();
    } catch {
      // Ignore malformed URLs
    }
  }

  return event;
}

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_APP_ENVIRONMENT ?? "development",
  tracesSampleRate: 0.1,
  debug: false,
  beforeSend(event) {
    return scrubSentryEvent(event) as Sentry.ErrorEvent;
  },
});
