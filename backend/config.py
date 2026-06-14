import os
from dotenv import load_dotenv

load_dotenv()

UF_API_KEY = os.getenv("UF_API_KEY")
UF_BASE_URL = os.getenv("UF_BASE_URL", "https://api.ai.it.ufl.edu/v1")
CALLMEBOT_NUMBERS_RAW = os.getenv("CALLMEBOT_NUMBERS")
CALLMEBOT_API_KEYS_RAW = os.getenv("CALLMEBOT_API_KEYS")
NVIDIA_VISION_API_KEY = os.getenv("NVIDIA_VISION_API_KEY")
NVIDIA_TEXT_API_KEY = os.getenv("NVIDIA_TEXT_API_KEY")

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

if not NVIDIA_VISION_API_KEY:
    raise ValueError("Missing NVIDIA_VISION_API_KEY environment variable")

if not NVIDIA_TEXT_API_KEY:
    raise ValueError("Missing NVIDIA_TEXT_API_KEY environment variable")

if not CALLMEBOT_NUMBERS_RAW or not CALLMEBOT_API_KEYS_RAW:
    raise ValueError("Missing CallMeBot configuration environment variables")

CALLMEBOT_NUMBERS = [num.strip() for num in CALLMEBOT_NUMBERS_RAW.split(",") if num.strip()]
CALLMEBOT_API_KEYS = [key.strip() for key in CALLMEBOT_API_KEYS_RAW.split(",") if key.strip()]

if len(CALLMEBOT_NUMBERS) != len(CALLMEBOT_API_KEYS):
    raise ValueError("CALLMEBOT_NUMBERS and CALLMEBOT_API_KEYS must have the same length")
