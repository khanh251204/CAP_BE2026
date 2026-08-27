import bcrypt

def get_password_hash(password: str) -> str:
    """
    MÃ£ hÃ³a máº­t kháº©u - TÆ°Æ¡ng tá»± bcrypt.hash()
    """
    # Chuyá»ƒn password sang dáº¡ng bytes
    pwd_bytes = password.encode('utf-8')
    # Táº¡o salt vÃ  hash
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Tráº£ vá» dáº¡ng string Ä‘á»ƒ lÆ°u vÃ o DB
    return hashed_password.decode('utf-8')

def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:

    if not hashed_password:
        return False

    try:

        password_byte = (
            plain_password.encode("utf-8")
        )

        hashed_byte = (
            hashed_password.encode("utf-8")
        )

        return bcrypt.checkpw(
            password_byte,
            hashed_byte
        )

    except (
        ValueError,
        TypeError
    ):
        return False
