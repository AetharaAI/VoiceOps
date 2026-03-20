from app.schemas.campaign import OutboundCampaignCreate


def test_outbound_campaign_create_defaults() -> None:
    payload = OutboundCampaignCreate(
        name='Demo Recovery Campaign',
        objective='Recover missed demo requests.',
        opening_line='Hi, this is Maya calling from Syndicate AI.',
    )

    assert payload.qualification_fields == {}
    assert payload.retry_rules == {}
    assert payload.voicemail_config == {}
    assert payload.handoff_rules == {}
    assert payload.crm_mapping == {}
    assert payload.model_config == {}
    assert payload.tts_config == {}
    assert payload.is_active is True
