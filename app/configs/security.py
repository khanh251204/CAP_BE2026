import bcrypt

def get_password_hash(password: str) -> str:
    """
    Mã hóa mật khẩu - Tương tự bcrypt.hash()
    Bcrypt giới hạn tối đa 72 bytes; cắt tối đa 72 bytes để tránh ValueError / 500 khi password dài.
    """
    # Chuyển password sang dạng bytes và giới hạn 72 bytes theo quy định của bcrypt
    pwd_bytes = password.encode('utf-8')[:72]
    # Tạo salt và hash
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Trả về dạng string để lưu vào DB
    return hashed_password.decode('utf-8')

def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:

    if not hashed_password:
        return False

    try:
        password_byte = plain_password.encode("utf-8")[:72]
        hashed_byte = hashed_password.encode("utf-8")

        return bcrypt.checkpw(
            password_byte,
            hashed_byte
        )

    except (
        ValueError,
        TypeError
    ):
        return False