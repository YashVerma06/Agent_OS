import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Agent OS — Workforce Control Room',
  description: 'Governed infrastructure for creating and operating AI workforces.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
