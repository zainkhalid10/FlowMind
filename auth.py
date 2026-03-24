from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import os
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import SessionLocal, User, Project, ProjectMember

# JWT settings - use environment variable for security
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
if SECRET_KEY == "your-secret-key-change-this-in-production":
    # Generate a new key if still using default
    SECRET_KEY = secrets.token_urlsafe(32)
    print("⚠️ WARNING: Using auto-generated SECRET_KEY. Set SECRET_KEY environment variable for production!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

# HTTP Bearer token
security = HTTPBearer()


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt. Bcrypt has a 72-byte limit, so we truncate if needed."""
    # Bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        # Try bcrypt first (new format - starts with $2b$ or $2a$)
        if hashed_password.startswith('$2'):
            # Truncate password to 72 bytes for bcrypt
            password_bytes = plain_password.encode('utf-8')
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            
            hashed_bytes = hashed_password.encode('utf-8')
            if bcrypt.checkpw(password_bytes, hashed_bytes):
                return True
        
        # Fallback: Check if it's old SHA-256 format (for migration)
        # Old format: "salt:hash"
        if ':' in hashed_password and len(hashed_password.split(':')) == 2 and not hashed_password.startswith('$2'):
            # Old format detected - verify using old method for backward compatibility
            import hashlib
            import secrets
            parts = hashed_password.split(':')
            if len(parts) != 2:
                return False
            salt, stored_hash = parts
            
            original_password_bytes = plain_password.encode('utf-8')
            salt_bytes = salt.encode('utf-8')
            hash_obj = hashlib.sha256()
            hash_obj.update(original_password_bytes)
            hash_obj.update(salt_bytes)
            computed_hash = hash_obj.hexdigest()
            
            return secrets.compare_digest(computed_hash, stored_hash)
        
        return False
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token. data may include sub, role, team_id."""
    to_encode = data.copy()
    # JWT requires 'sub' to be a string, so convert if it's an int
    if "sub" in to_encode and isinstance(to_encode["sub"], int):
        to_encode["sub"] = str(to_encode["sub"])
    if "team_id" in to_encode and to_encode["team_id"] is not None:
        to_encode["team_id"] = int(to_encode["team_id"])
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        # Convert string back to int (JWT requires sub to be string)
        user_id = int(user_id_str)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if user.is_active == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


def get_visible_user_ids(user: User, db: Session) -> list:
    """Return list of user IDs the current user is allowed to see.
    Manager: all active users. Team head: same team members. Member: only self."""
    if getattr(user, "role", None) == "manager":
        return [u.id for u in db.query(User).filter(User.is_active == 1).all()]
    if getattr(user, "role", None) == "team_head" and getattr(user, "team_id", None):
        return [u.id for u in db.query(User).filter(User.team_id == user.team_id, User.is_active == 1).all()]
    return [user.id]


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get the current user if authenticated, otherwise return None."""
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        # Convert string back to int (JWT requires sub to be string)
        user_id = int(user_id_str)
    except (JWTError, ValueError, TypeError):
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.is_active == 0:
        return None
    
    return user


def can_user_access_project(user: User, project_id: int, db: Session) -> bool:
    """Return True if user can access a project by ownership, membership, or manager role."""
    if project_id is None:
        return False
    if getattr(user, "role", None) == "manager":
        return db.query(Project).filter(Project.id == project_id).first() is not None

    owned = db.query(Project).filter(Project.id == project_id, Project.created_by == user.id).first()
    if owned:
        return True

    membership = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id,
    ).first()
    return membership is not None

