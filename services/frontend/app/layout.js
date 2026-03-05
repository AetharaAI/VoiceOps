import './globals.css';

export const metadata = {
  title: 'Aether VoiceOps',
  description: 'Multi-tenant AI voice agent operations platform'
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className="bg-glow" />
        {children}
      </body>
    </html>
  );
}
