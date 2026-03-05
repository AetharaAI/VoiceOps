import Link from 'next/link';

export default function Home() {
  return (
    <main className="container">
      <h1>Aether VoiceOps</h1>
      <p>Production-oriented voice-agent platform with multi-tenant control plane.</p>
      <div className="card">
        <p>Start with login, then configure tenant settings, agents, forms, and call workflows.</p>
        <Link href="/login">Go to Login</Link>
      </div>
    </main>
  );
}
