import asyncio
import httpx
import urllib.parse
import logging
from typing import List

from config import CALLMEBOT_NUMBERS, CALLMEBOT_API_KEYS
from models import WhatsAppStatus

logger = logging.getLogger(__name__)


async def send_whatsapp_message(number: str, api_key: str, message: str) -> WhatsAppStatus:
    encoded_message = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={number}&text={encoded_message}&apikey={api_key}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"Sending WhatsApp message to {number}")
            response = await client.get(url)

            if response.status_code == 200:
                logger.info(f"Successfully sent WhatsApp message to {number}")
                return WhatsAppStatus(number=number, success=True)
            else:
                logger.error(f"Failed to send to {number}. Status: {response.status_code}, Body: {response.text}")
                return WhatsAppStatus(number=number, success=False, error_message=f"HTTP {response.status_code}")

    except Exception as e:
        logger.error(f"Exception sending WhatsApp message to {number}: {e}")
        return WhatsAppStatus(number=number, success=False, error_message=str(e))


async def send_to_all(message: str) -> List[WhatsAppStatus]:
    pairs = list(zip(CALLMEBOT_NUMBERS, CALLMEBOT_API_KEYS))
    tasks = [send_whatsapp_message(number, api_key, message) for number, api_key in pairs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    statuses = []
    for (number, _), res in zip(pairs, results):
        if isinstance(res, Exception):
            # Should not normally reach here since the coroutine catches all exceptions,
            # but guard against any unexpected failure outside the coroutine body.
            logger.error(f"Unexpected gather error for {number}: {res}")
            statuses.append(WhatsAppStatus(number=number, success=False, error_message=str(res)))
        else:
            statuses.append(res)

    return statuses
