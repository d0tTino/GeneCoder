import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SocketIOManager } from "@/components/SocketIOManager";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Automated Testing Agent Demo",
  description: "Automated Testing Agent Demo using the OpenAI CUA model",
  icons: { icon: "/openai_logo.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} antialiased`}>
        <SocketIOManager />

        <div className="flex flex-col h-screen overflow-hidden bg-gray-50 text-gray-900">
          <main className="flex-1 min-h-0 flex flex-col">{children}</main>
        </div>
      </body>
    </html>
  );
}
