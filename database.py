from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from pathlib import Path

# -------------------- DB Setup --------------------
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "flowmind.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

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
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)  # Optional project scope
    created_at = Column(DateTime, default=datetime.utcnow)  # Track when file was uploaded
    view_id = Column(String(255), nullable=True, index=True)  # For AI agent results

    # One-to-many relationship with image metadata
    images = relationship("ImageMeta", back_populates="file")
    # Relationship to user
    user = relationship("User", backref="parsed_files")
    project = relationship("Project", backref="parsed_files")


# -------------------- Image Metadata Table --------------------
class ImageMeta(Base):
    __tablename__ = "image_meta"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("parsed_files.id"))
    image_path = Column(String(512))
    page_number = Column(Integer)
    ocr_text = Column(Text)

    file = relationship("ParsedFile", back_populates="images")


# -------------------- Team Table --------------------
class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("User", back_populates="team", foreign_keys="User.team_id")


# -------------------- Project Tables --------------------
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(30), default="draft", nullable=False)  # draft | active | completed | archived
    workflow_stage = Column(String(40), default="requirements_extraction", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", backref="owned_projects", foreign_keys=[created_by])


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role_in_project = Column(String(30), default="member", nullable=False)  # client | project_manager | team_head | member
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", backref="memberships")
    user = relationship("User", backref="project_memberships")


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    feature_id = Column(Integer, ForeignKey("features.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), default="todo", nullable=False)  # todo | in_progress | blocked | done
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    due_date = Column(DateTime, nullable=True)
    daily_update = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", backref="tasks")
    feature = relationship("Feature", backref="tasks", foreign_keys=[feature_id])
    assignee = relationship("User", backref="tasks_assigned", foreign_keys=[assigned_to_user_id])
    creator = relationship("User", backref="tasks_created", foreign_keys=[created_by])


# -------------------- User Table --------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Nullable for OAuth-only accounts
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)  # 1 for active, 0 for inactive
    role = Column(String(20), default="manager", nullable=False)  # manager | client
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    
    # OAuth fields
    google_id = Column(String(255), nullable=True, unique=True, index=True)  # Google's unique ID
    oauth_provider = Column(String(50), nullable=True)  # 'google', etc.
    oauth_profile_picture = Column(String(512), nullable=True)  # Store profile picture URL
    oauth_verified_at = Column(DateTime, nullable=True)  # When OAuth was verified

    team = relationship("Team", back_populates="members", foreign_keys=[team_id])


# -------------------- Feature Table --------------------
class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    file_id = Column(Integer, ForeignKey("parsed_files.id"), nullable=True, index=True)
    category = Column(String(100))  # functional, non-functional, user, business
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default="Medium")  # High | Medium | Low
    source = Column(String(40), default="system")  # system | client | client_approved
    client_review_status = Column(String(40), default="pending")  # pending | approved | rejected | modification_requested | pending_manager_approval
    status = Column(String(20), default="pending")  # pending, approved, denied
    quality_score = Column(Integer, default=0)
    feedback = Column(Text, nullable=True)  # Client feedback on the requirement
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Team head/manager assigns to member
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="features", foreign_keys=[user_id])
    assigned_to = relationship("User", backref="assigned_features", foreign_keys=[assigned_to_user_id])
    file = relationship("ParsedFile", backref="features")
    project = relationship("Project", backref="features")


# -------------------- Client Review Assignment Table --------------------
class ReviewAssignment(Base):
    __tablename__ = "review_assignments"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("parsed_files.id"), nullable=False, index=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    temp_password = Column(String(255), nullable=True)
    due_date = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    file = relationship("ParsedFile", foreign_keys=[file_id], backref="review_assignments")
    manager = relationship("User", foreign_keys=[manager_id], backref="review_assignments_created")
    client = relationship("User", foreign_keys=[client_id], backref="review_assignments_received")


# -------------------- Client Review Feedback Table --------------------
class ReviewFeedback(Base):
    __tablename__ = "review_feedback"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("parsed_files.id"), nullable=False, index=True)
    req_id = Column(Integer, ForeignKey("features.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(40), nullable=False)  # approve | reject | request_modification
    comment = Column(Text, nullable=True)
    resolved = Column(Integer, default=0)
    manager_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    file = relationship("ParsedFile", foreign_keys=[file_id], backref="review_feedback")
    feature = relationship("Feature", foreign_keys=[req_id], backref="review_feedback")
    client = relationship("User", foreign_keys=[client_id], backref="review_feedback")


# -------------------- Integration Config (Trello/Jira credentials - manager only) --------------------
class IntegrationConfig(Base):
    __tablename__ = "integration_config"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(20), nullable=False, unique=True)  # trello | jira
    key_name = Column(String(64), nullable=False)  # e.g. api_key, token, list_id
    value = Column(Text, nullable=True)  # encrypted or plain - restrict access to manager
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# -------------------- Integration Log (D2: Task Integration Log) --------------------
class IntegrationLog(Base):
    __tablename__ = "integration_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    platform = Column(String(20), nullable=False)  # trello | jira
    source = Column(String(20), nullable=False)  # view | approved
    source_id = Column(String(255), nullable=True)  # view_id or null for approved
    items_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # JSON: per-item result with url/key or error
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="integration_logs")


# -------------------- AI Agent Chat History --------------------
class AgentChatHistory(Base):
    __tablename__ = "agent_chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    file_id = Column(Integer, ForeignKey("parsed_files.id"), nullable=True, index=True)
    filename = Column(String(255), nullable=True)
    user_message = Column(Text, nullable=True)
    assistant_message = Column(Text, nullable=False)
    view_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="agent_chat_history")
    project = relationship("Project", backref="agent_chat_history")
    file = relationship("ParsedFile", backref="agent_chat_history")


# -------------------- Initialize Database --------------------
def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_add_role_team()
    _migrate_user_oauth_columns()
    _migrate_add_assigned_to()
    _migrate_feature_review_columns()
    _migrate_project_columns()
    _migrate_integration_tables()
    _migrate_project_tables()
    _migrate_review_tables()
    _migrate_review_assignment_password_column()
    _migrate_agent_chat_history_table()
    seed_teams_if_empty()


def seed_teams_if_empty():
    """Create default team if no teams exist."""
    db = SessionLocal()
    try:
        if db.query(Team).count() == 0:
            db.add(Team(name="Default", description="Default team"))
            db.commit()
    except Exception as e:
        print(f"Seed teams note: {e}")
    finally:
        db.close()


def _migrate_add_role_team():
    """Add role and team_id to users if they don't exist (for existing DBs)."""
    from sqlalchemy import inspect, text
    conn = engine.connect()
    try:
        insp = inspect(engine)
        if "users" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("users")]
        if "role" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'manager'"))
            conn.commit()
            conn.execute(text("UPDATE users SET role = 'manager' WHERE role IS NULL"))
            conn.commit()
        if "team_id" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN team_id INTEGER"))
            conn.commit()
    except Exception as e:
        print(f"Migration note: {e}")
    finally:
        conn.close()


def _migrate_add_assigned_to():
    """Add assigned_to_user_id to features if missing."""
    from sqlalchemy import inspect, text
    conn = engine.connect()
    try:
        insp = inspect(engine)
        if "features" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("features")]
        if "assigned_to_user_id" not in cols:
            conn.execute(text("ALTER TABLE features ADD COLUMN assigned_to_user_id INTEGER"))
            conn.commit()
    except Exception as e:
        print(f"Migration assigned_to note: {e}")
    finally:
        conn.close()


def _migrate_user_oauth_columns():
    """Add OAuth-related columns and index to users if missing."""
    from sqlalchemy import inspect, text

    conn = engine.connect()
    try:
        insp = inspect(engine)
        if "users" not in insp.get_table_names():
            return

        cols = [c["name"] for c in insp.get_columns("users")]
        if "google_id" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(255)"))
            conn.commit()
        if "oauth_provider" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(50)"))
            conn.commit()
        if "oauth_profile_picture" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN oauth_profile_picture VARCHAR(512)"))
            conn.commit()
        if "oauth_verified_at" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN oauth_verified_at DATETIME"))
            conn.commit()

        indexes = [idx["name"] for idx in insp.get_indexes("users")]
        if "ix_users_google_id" not in indexes:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id)"))
            conn.commit()
    except Exception as e:
        print(f"Migration oauth columns note: {e}")
    finally:
        conn.close()


def _migrate_integration_tables():
    """Create integration_config and integration_log if they don't exist."""
    from sqlalchemy import inspect
    insp = inspect(engine)
    tables = insp.get_table_names()
    if "integration_config" not in tables or "integration_log" not in tables:
        Base.metadata.create_all(bind=engine, tables=[IntegrationConfig.__table__, IntegrationLog.__table__])


def _migrate_project_columns():
    """Add project_id columns to parsed_files/features if missing."""
    from sqlalchemy import inspect, text
    conn = engine.connect()
    try:
        insp = inspect(engine)
        tables = insp.get_table_names()

        if "parsed_files" in tables:
            parsed_cols = [c["name"] for c in insp.get_columns("parsed_files")]
            if "project_id" not in parsed_cols:
                conn.execute(text("ALTER TABLE parsed_files ADD COLUMN project_id INTEGER"))
                conn.commit()

        if "features" in tables:
            feature_cols = [c["name"] for c in insp.get_columns("features")]
            if "project_id" not in feature_cols:
                conn.execute(text("ALTER TABLE features ADD COLUMN project_id INTEGER"))
                conn.commit()
    except Exception as e:
        print(f"Migration project columns note: {e}")
    finally:
        conn.close()


def _migrate_project_tables():
    """Create project workflow tables if they do not exist."""
    from sqlalchemy import inspect
    insp = inspect(engine)
    tables = insp.get_table_names()
    needed = []
    if "projects" not in tables:
        needed.append(Project.__table__)
    if "project_members" not in tables:
        needed.append(ProjectMember.__table__)
    if "project_tasks" not in tables:
        needed.append(ProjectTask.__table__)
    if needed:
        Base.metadata.create_all(bind=engine, tables=needed)


def _migrate_feature_review_columns():
    """Add review-related columns to features if missing."""
    from sqlalchemy import inspect, text
    conn = engine.connect()
    try:
        insp = inspect(engine)
        if "features" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("features")]
        if "title" not in cols:
            conn.execute(text("ALTER TABLE features ADD COLUMN title VARCHAR(255)"))
            conn.commit()
        if "priority" not in cols:
            conn.execute(text("ALTER TABLE features ADD COLUMN priority VARCHAR(20) DEFAULT 'Medium'"))
            conn.commit()
        if "source" not in cols:
            conn.execute(text("ALTER TABLE features ADD COLUMN source VARCHAR(40) DEFAULT 'system'"))
            conn.commit()
        if "client_review_status" not in cols:
            conn.execute(text("ALTER TABLE features ADD COLUMN client_review_status VARCHAR(40) DEFAULT 'pending'"))
            conn.commit()
    except Exception as e:
        print(f"Migration feature review columns note: {e}")
    finally:
        conn.close()


def _migrate_review_tables():
    """Create review assignment and feedback tables if they don't exist."""
    from sqlalchemy import inspect
    insp = inspect(engine)
    tables = insp.get_table_names()
    needed = []
    if "review_assignments" not in tables:
        needed.append(ReviewAssignment.__table__)
    if "review_feedback" not in tables:
        needed.append(ReviewFeedback.__table__)
    if needed:
        Base.metadata.create_all(bind=engine, tables=needed)


def _migrate_review_assignment_password_column():
    """Add temp_password column to review_assignments if missing."""
    from sqlalchemy import inspect, text

    conn = engine.connect()
    try:
        insp = inspect(engine)
        if "review_assignments" not in insp.get_table_names():
            return

        cols = [c["name"] for c in insp.get_columns("review_assignments")]
        if "temp_password" not in cols:
            conn.execute(text("ALTER TABLE review_assignments ADD COLUMN temp_password VARCHAR(255)"))
            conn.commit()
    except Exception as e:
        print(f"Migration review assignment password note: {e}")
    finally:
        conn.close()


def _migrate_agent_chat_history_table():
    """Create agent_chat_history table if it does not exist."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    tables = insp.get_table_names()
    if "agent_chat_history" not in tables:
        Base.metadata.create_all(bind=engine, tables=[AgentChatHistory.__table__])
