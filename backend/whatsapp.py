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
                logger.error(f"Failed to send to {number}. Status Code: {response.status_code}, Body: {response.text}")
                return WhatsAppStatus(number=number, success=False, error_message=f"Status: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Exception sending WhatsApp message to {number}: {e}")
        return WhatsAppStatus(number=number, success=False, error_message=str(e))

async def send_to_all(message: str) -> List[WhatsAppStatus]:
    tasks = []
    
    for number, api_key in zip(CALLMEBOT_NUMBERS, CALLMEBOT_API_KEYS):
        tasks.append(send_whatsapp_message(number, api_key, message))
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    statuses = []
    for res in results:
        if isinstance(res, Exception):
            logger.error(f"Gather returned exception: {res}")
            # we don't have the number easily here if it fails outside the coroutine, but our coroutine catches exceptions.
        elif isinstance(res, WhatsAppStatus):
            statuses.append(res)
            
    return statuses
