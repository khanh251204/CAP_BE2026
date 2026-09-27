import os
from dotenv import load_dotenv
import cloudinary

load_dotenv()

def get_env_cleaned(key: str, default: str = "") -> str:
    val = os.getenv(key, default)
    if val:
        return val.strip().strip("'\"")
    return default

CLOUDINARY_NAME = get_env_cleaned("CLOUDINARY_NAME") or get_env_cleaned("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = get_env_cleaned("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = get_env_cleaned("CLOUDINARY_API_SECRET")

if CLOUDINARY_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )
