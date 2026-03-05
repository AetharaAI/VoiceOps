'use client';

import { useEffect, useState } from 'react';
import Nav from '../../components/nav';
import { api } from '../../lib/api';

const defaultSchema = {
  title: 'Intake Form',
  fields: [
    { id: 'name', type: 'text', label: 'Full Name', required: true },
    { id: 'phone', type: 'phone', label: 'Phone', required: true },
    { id: 'appointment_type', type: 'select', options: ['Consult', 'Repair', 'Support'] }
  ]
};

const defaultWorkflow = {
  on_submit: {
    action: 'call_now',
    agent_id: '',
    webhook_url: ''
  }
};

export default function FormsPage() {
  const [forms, setForms] = useState([]);
  const [message, setMessage] = useState('');
  const [formName, setFormName] = useState('Inbound Intake');
  const [schemaText, setSchemaText] = useState(JSON.stringify(defaultSchema, null, 2));
  const [workflowText, setWorkflowText] = useState(JSON.stringify(defaultWorkflow, null, 2));

  const [submitFormId, setSubmitFormId] = useState('');
  const [submitPayload, setSubmitPayload] = useState(
    JSON.stringify({ name: 'Jordan Reed', phone: '+15551230001', appointment_type: 'Consult' }, null, 2)
  );

  useEffect(() => {
    loadForms();
  }, []);

  async function loadForms() {
    try {
      const data = await api('/forms');
      setForms(data);
      if (!submitFormId && data.length > 0) setSubmitFormId(data[0].id);
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function createForm(e) {
    e.preventDefault();
    try {
      await api('/forms', {
        method: 'POST',
        body: JSON.stringify({
          name: formName,
          schema: JSON.parse(schemaText),
          workflow_config: JSON.parse(workflowText)
        })
      });
      await loadForms();
      setMessage('Form created.');
    } catch (err) {
      setMessage(`Create failed: ${err.message}`);
    }
  }

  async function submitForm(e) {
    e.preventDefault();
    try {
      const data = await api(`/forms/${submitFormId}/submit`, {
        method: 'POST',
        body: JSON.stringify({ payload: JSON.parse(submitPayload) })
      });
      setMessage(`Form submitted. linked_call_id=${data.linked_call_id || 'none'}`);
    } catch (err) {
      setMessage(`Submit failed: ${err.message}`);
    }
  }

  return (
    <main className="container">
      <Nav />
      <h1>Forms Builder</h1>
      <div className="grid-2">
        <section className="card">
          <h2>Create Form Schema</h2>
          <form onSubmit={createForm}>
            <label>Form Name</label>
            <input value={formName} onChange={(e) => setFormName(e.target.value)} />
            <label>Schema JSON</label>
            <textarea value={schemaText} onChange={(e) => setSchemaText(e.target.value)} />
            <label>Workflow JSON</label>
            <textarea value={workflowText} onChange={(e) => setWorkflowText(e.target.value)} />
            <button type="submit">Create Form</button>
          </form>
        </section>

        <section className="card">
          <h2>Submit Form</h2>
          <form onSubmit={submitForm}>
            <label>Form ID</label>
            <select value={submitFormId} onChange={(e) => setSubmitFormId(e.target.value)}>
              <option value="">Select form</option>
              {forms.map((f) => (
                <option value={f.id} key={f.id}>
                  {f.name} ({f.id})
                </option>
              ))}
            </select>
            <label>Payload JSON</label>
            <textarea value={submitPayload} onChange={(e) => setSubmitPayload(e.target.value)} />
            <button className="secondary" type="submit">Submit + Trigger Workflow</button>
          </form>
        </section>
      </div>

      <section className="card">
        <h2>Existing Forms</h2>
        <pre>{JSON.stringify(forms, null, 2)}</pre>
      </section>

      <section className="card">{message || 'Ready.'}</section>
    </main>
  );
}
