import httpx


class WorkflowEngine:
    async def execute_form_submission(self, workflow_config: dict, payload: dict) -> dict:
        action = workflow_config.get('on_submit', {}).get('action', 'none')
        if action == 'call_now':
            return {'action': 'call_now', 'context_payload': payload}
        if action == 'schedule_call':
            return {
                'action': 'schedule_call',
                'schedule_at': workflow_config.get('on_submit', {}).get('schedule_at'),
                'context_payload': payload,
            }
        if action == 'send_sms_link':
            webhook = workflow_config.get('on_submit', {}).get('webhook_url')
            if webhook:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(webhook, json={'payload': payload})
            return {'action': 'send_sms_link'}
        return {'action': 'none'}

    async def run_post_call_actions(self, workflow_dsl: dict, call_context: dict) -> list[dict]:
        actions: list[dict] = []
        for node in workflow_dsl.get('post_call', []):
            if node.get('type') == 'webhook':
                url = node.get('url')
                if url:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(url, json=call_context)
                    actions.append({'type': 'webhook', 'status': 'sent', 'url': url})
            elif node.get('type') == 'ticket':
                actions.append({'type': 'ticket', 'status': 'queued'})
        return actions


workflow_engine = WorkflowEngine()
