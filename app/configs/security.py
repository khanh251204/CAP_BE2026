import bcrypt

def get_password_hash(password: str) -> str:
    """
    Mã hóa mật khẩu - Tương tự bcrypt.hash()
    """
    # Chuyển password sang dạng bytes
    pwd_bytes = password.encode('utf-8')
    # Tạo salt và hash
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Trả về dạng string để lưu vào DB
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Kiểm tra mật khẩu - Tương tự bcrypt.compare()
    """
    try:
        # Chuyển cả 2 về dạng bytes để bcrypt so sánh
        password_byte = plain_password.encode('utf-8')
        hashed_byte = hashed_password.encode('utf-8')
        
        return bcrypt.checkpw(password_byte, hashed_byte)
    except Exception as e:
        print(f"❌ Lỗi verify password: {e}")
        return False