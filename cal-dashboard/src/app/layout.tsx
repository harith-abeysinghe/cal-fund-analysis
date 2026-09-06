import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'CAL Fund Dashboard',
  description: 'CAL fund CSV charts and refresh UI',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
