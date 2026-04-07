import { withSentryConfig } from "@sentry/nextjs";
import withBundleAnalyzer from "@next/bundle-analyzer";

const bundleAnalyzer = withBundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

const sentryOptions = {
  silent: true,
  unstable_ignoreErrors: true,
  disableClientWebpackPlugin: false,
  disableServerWebpackPlugin: false,
};

const hasSentryDsn = Boolean(process.env.SENTRY_DSN?.trim());

const finalConfig = hasSentryDsn
  ? withSentryConfig(nextConfig, sentryOptions)
  : nextConfig;

export default bundleAnalyzer(finalConfig);
