import type { Metadata } from "next";
import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "JobLantern — Light Your Career Path",
  description: "Lighting your path through a dark & confusing job search process directly to your ideal role.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable} min-h-full flex flex-col bg-[#0A0F0D] text-[#EDEFEA]`}>
        {children}
      </body>
    </html>
  );
}
