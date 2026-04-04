import localFont from "next/font/local";
import "./globals.css";
import { defaultMetadata } from "@/lib/metadata";
import { AppProviders } from "@/app/providers";
import { CookieConsent } from "@/components/legal/CookieConsent";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-mono",
  weight: "100 900",
});

export const metadata = defaultMetadata;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[9999] focus:px-4 focus:py-2 focus:bg-background focus:text-foreground focus:border focus:border-border focus:rounded-md focus:text-sm focus:font-medium focus:shadow-md"
        >
          Skip to main content
        </a>
        <AppProviders>{children}</AppProviders>
        <CookieConsent />
      </body>
    </html>
  );
}
