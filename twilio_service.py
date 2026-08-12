import httpx
from typing import Optional
from fastapi import Response
from twilio.rest import Client
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER

def get_twilio_client() -> Optional[Client]:
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return None

async def fetch_twilio_media(media_url: str) -> Optional[bytes]:
    try:
        auth = None
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        async with httpx.AsyncClient() as client:
            res = await client.get(media_url, auth=auth, follow_redirects=True)
            if res.status_code == 200:
                return res.content
    except Exception as e:
        print(f"Error fetching Twilio media attachment: {e}")
    return None

def send_whatsapp_notification(to_number: str, message_text: str) -> bool:
    twilio_client = get_twilio_client()
    if not twilio_client:
        print("Twilio client not configured.")
        return False
    try:
        twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=message_text,
            to=to_number
        )
        return True
    except Exception as e:
        print(f"Error sending Twilio WhatsApp notification: {e}")
        return False

def build_twiml_response(message_text: str) -> Response:
    xml_content = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Message>{message_text}</Message></Response>"
    return Response(content=xml_content, media_type="application/xml")
