from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from database import Base

class Connector(Base):
    __tablename__ = "connectors"
    
    id = Column(String, primary_key=True)
    user_phone = Column(String, unique=True, index=True) # Used as account_id
    connector_type = Column(String)
    status = Column(String)
    last_sync_message_id = Column(Integer, nullable=True)


class OAuthState(Base):
    """Single-use, server-side OAuth state token for the Google Photos flow.

    Replaces the previous INSECURE pattern of using the account_id directly as
    the OAuth `state`. A cryptographically-random state is minted per login,
    mapped to the resolved account, and consumed exactly once at callback time.
    Additive table — does not affect Telegram/local or any existing table.
    """
    __tablename__ = "oauth_states"

    state = Column(String, primary_key=True)
    account_id = Column(String, index=True)
    created_at = Column(DateTime)
    used = Column(Integer, default=0)  # 0 = unused, 1 = consumed (single-use)

class Image(Base):
    __tablename__ = "images"

    id = Column(String, primary_key=True, index=True)
    original_filename = Column(String)
    stored_path = Column(String)
    source = Column(String, nullable=True)
    mime_type = Column(String)
    file_size = Column(Integer)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    captured_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime)
    processing_status = Column(String) # pending | processing | ready | failed
    processing_error = Column(String, nullable=True)
    # Account ownership (additive/deferred — see design "Image account_id — deferred").
    # Uploads are not served through retrieval, so served-image ownership is the
    # Chroma account_id tag; this column exists so GET /api/images/{id}/status can
    # be scoped in a later phase. Left NULL for pre-existing rows (never fabricated).
    account_id = Column(String, nullable=True, index=True)
    
    source_type = Column(String, default='local')
    source_metadata = Column(String, nullable=True)

class ImageText(Base):
    __tablename__ = "image_texts"
    
    image_id = Column(String, ForeignKey("images.id"), primary_key=True)
    ocr_text = Column(String)
    ocr_engine = Column(String)
    processed_at = Column(DateTime)

class ImageEmbedding(Base):
    __tablename__ = "image_embeddings"
    
    image_id = Column(String, ForeignKey("images.id"), primary_key=True)
    embedding_model = Column(String)
    vector_store_id = Column(String)
    processed_at = Column(DateTime)

class SearchSession(Base):
    __tablename__ = "search_sessions"
    
    id = Column(String, primary_key=True, index=True)
    # Single owning account (indexed). Set at creation to the resolved account;
    # never null/anonymous/previous/global for backend-created conversations.
    account_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    active_query = Column(String)

class SearchMessage(Base):
    __tablename__ = "search_messages"
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("search_sessions.id"))
    # Denormalized owner for defense-in-depth (indexed).
    account_id = Column(String, nullable=True, index=True)
    role = Column(String) # user | assistant
    content = Column(String)
    created_at = Column(DateTime)

class SearchContext(Base):
    __tablename__ = "search_contexts"
    
    session_id = Column(String, ForeignKey("search_sessions.id"), primary_key=True)
    account_id = Column(String, nullable=True)
    original_intent = Column(String)
    topic_clues = Column(String)
    content_clues = Column(String)
    visual_clues = Column(String)
    metadata_filters = Column(String)
    updated_query = Column(String)

class SearchResultRef(Base):
    """One persisted reference to a retrieved memory within a search/refine turn.

    Deliberately stores ONLY display-safe fields: image_id, rank, and a small
    JSON of displayable metadata. There is intentionally NO file_path /
    absolute_path / source_root / binary column (R4.5) — the served URL is
    derived from image_id alone at read time.
    """
    __tablename__ = "search_result_refs"

    id = Column(String, primary_key=True, index=True)
    message_id = Column(String, ForeignKey("search_messages.id"), index=True)
    session_id = Column(String, index=True)
    account_id = Column(String, nullable=True, index=True)
    image_id = Column(String)
    rank = Column(Integer)
    display_metadata_json = Column(String)
