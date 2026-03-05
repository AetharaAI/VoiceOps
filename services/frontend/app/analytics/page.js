'use client';

import { useEffect, useState } from 'react';
import Nav from '../../components/nav';
import { api } from '../../lib/api';

export default function AnalyticsPage() {
  const [summary, setSummary] = useState(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const data = await api('/analytics/summary');
      setSummary(data);
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <main className="container">
      <Nav />
      <h1>Analytics</h1>
      {!summary ? (
        <section className="card">{message || 'Loading KPI summary...'}</section>
      ) : (
        <div className="grid-2">
          <section className="card">
            <h2>Total Calls</h2>
            <div className="kpi">{summary.total_calls}</div>
          </section>
          <section className="card">
            <h2>Completed Calls</h2>
            <div className="kpi">{summary.completed_calls}</div>
          </section>
          <section className="card">
            <h2>Containment Rate</h2>
            <div className="kpi">{(summary.containment_rate * 100).toFixed(2)}%</div>
          </section>
          <section className="card">
            <h2>Booking Rate</h2>
            <div className="kpi">{(summary.booking_rate * 100).toFixed(2)}%</div>
          </section>
          <section className="card">
            <h2>Escalation Rate</h2>
            <div className="kpi">{(summary.escalation_rate * 100).toFixed(2)}%</div>
          </section>
          <section className="card">
            <h2>Avg Handle Time</h2>
            <div className="kpi">{summary.avg_handle_seconds}s</div>
          </section>
        </div>
      )}
      <section className="card" style={{ marginTop: 14 }}>
        <button onClick={load}>Refresh</button>
      </section>
    </main>
  );
}
