from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class OutboundCallResult:
    external_call_id: str
    status: str


class TelephonyProvider(ABC):
    @abstractmethod
    async def create_outbound_call(self, to_number: str, from_number: str, callback_url: str) -> OutboundCallResult:
        raise NotImplementedError


class TwilioProvider(TelephonyProvider):
    def __init__(self) -> None:
        self.settings = get_settings()

    async def create_outbound_call(self, to_number: str, from_number: str, callback_url: str) -> OutboundCallResult:
        if not self.settings.twilio_account_sid or not self.settings.twilio_auth_token:
            return OutboundCallResult(external_call_id='simulated-call-id', status='queued')

        twilio_url = (
            f'https://api.twilio.com/2010-04-01/Accounts/{self.settings.twilio_account_sid}/Calls.json'
        )
        data = {
            'To': to_number,
            'From': from_number,
            'Url': callback_url,
            'StatusCallback': f'{self.settings.public_base_url}/api/v1/webhooks/telephony/status',
            'StatusCallbackEvent': ['initiated', 'ringing', 'answered', 'completed'],
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                twilio_url,
                data=data,
                auth=(self.settings.twilio_account_sid, self.settings.twilio_auth_token),
            )
            response.raise_for_status()
            payload = response.json()
        return OutboundCallResult(external_call_id=payload['sid'], status=payload['status'])


def get_telephony_provider(provider_name: str = 'twilio') -> TelephonyProvider:
    if provider_name == 'twilio':
        return TwilioProvider()
    raise ValueError(f'Unsupported provider: {provider_name}')
