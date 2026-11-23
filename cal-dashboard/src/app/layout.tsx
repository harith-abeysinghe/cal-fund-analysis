import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'CAL Fund Dashboard',
  description: 'CAL unit trust price history, rankings and monthly allocation',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
