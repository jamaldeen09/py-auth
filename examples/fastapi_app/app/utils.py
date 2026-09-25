import bcrypt

def hash_password(password: str) -> str:
    """Hash a password using bcrypt for secure storage.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        The bcrypt hashed password as a string
    """
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash.
    
    Args:
        password: The plain text password to verify
        hashed_password: The bcrypt hashed password to compare against
        
    Returns:
        True if the password matches the hash, False otherwise
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))