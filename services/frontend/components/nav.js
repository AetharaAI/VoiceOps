'use client';

import Link from 'next/link';

export default function Nav() {
  return (
    <nav className="nav">
      <Link href="/dashboard">Dashboard</Link>
      <Link href="/agents">Agents</Link>
      <Link href="/forms">Forms</Link>
      <Link href="/calls">Calls</Link>
      <Link href="/analytics">Analytics</Link>
      <Link href="/login">Login</Link>
    </nav>
  );
}
