from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# -------------------- DB Setup --------------------
DATABASE_URL = "sqlite:///./flowmind.db"

# Optimize SQLite for better performance
engine = create_engine(
    DATABASE_URL, 
    connect_args={
        "check_same_thread": False,
        "timeout": 20  # 20 second timeout for database operations
    },
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,  # Maximum number of connections in pool
    max_overflow=20,  # Maximum overflow connections
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False  # Set to True for SQL query logging
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# -------------------- Parsed File Table --------------------
class ParsedFile(Base):
    __tablename__ = "parsed_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255))
    extracted_text = Column(Text)
    detected_shapes = Column(Integer)
    summary = Column(Text)
    full_text_path = Column(String(512))  # path to .txt file with full extracted text
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Link to user
    created_at = Column(DateTime, default=datetime.utcnow)  # Track when file was uploaded
    view_id = Column(String(255), nullable=True, index=True)  # For AI agent results

    # One-to-many relationship with image metadata
    images = relationship("ImageMeta", back_populates="file")
    # Relationship to user
    user = relationship("User", backref="parsed_files")


# -------------------- Image Metadata Table --------------------
class ImageMeta(Base):
    __tablename__ = "image_meta"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("parsed_files.id"))
    image_path = Column(String(512))
    page_number = Column(Integer)
    ocr_text = Column(Text)

    file = relationship("ParsedFile", back_populates="images")


# -------------------- User Table --------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)  # 1 for active, 0 for inactive


# -------------------- Feature Table --------------------
class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("parsed_files.id"), nullable=True, index=True)
    category = Column(String(100))  # functional, non-functional, user, business
    description = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # pending, approved, denied
    quality_score = Column(Integer, default=0)
    feedback = Column(Text, nullable=True)  # Client feedback on the requirement
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref="features")
    file = relationship("ParsedFile", backref="features")


# -------------------- Initialize Database --------------------
def init_db():
    Base.metadata.create_all(bind=engine)
