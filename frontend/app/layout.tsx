import type { Metadata } from 'next';
// import { Inter } from 'next/font/google';
import './globals.css';

// const inter = Inter({
//   subsets: ['latin'],
//   display: 'swap',
// });

export const metadata: Metadata = {
  title: 'Deforestation Monitor - Novo Progresso',
  description: 'Near real-time deforestation monitoring using Sentinel-1 SAR for Novo Progresso, Pará, Brazil',
  keywords: ['deforestation', 'SAR', 'Sentinel-1', 'Amazon', 'monitoring'],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>

      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
