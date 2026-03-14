import os
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://appuser:apppass@localhost:5432/visura_cache")

# For MySQL compatibility, we ensure the URL uses pymysql if needed
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
class Base(DeclarativeBase):
    pass

class Immobile(Base):
    __tablename__ = "immobili"
    
    id = Column(Integer, primary_key=True, index=True)
    provincia = Column(String(100), index=True)
    comune = Column(String(100), index=True)
    sezione = Column(String(50), nullable=True)
    foglio = Column(String(50), index=True)
    particella = Column(String(50), index=True)
    subalterno = Column(String(50), nullable=True)
    tipo_catasto = Column(String(1), index=True) # 'T' or 'F'
    
    categoria = Column(String(100), nullable=True)
    classe = Column(String(50), nullable=True)
    consistenza = Column(String(100), nullable=True)
    rendita = Column(String(100), nullable=True)
    indirizzo = Column(Text, nullable=True)
    partita = Column(String(100), nullable=True)
    
    valido_dal = Column(DateTime, default=datetime.utcnow)
    
    titolarita = relationship("Titolarita", back_populates="immobile")

class Soggetto(Base):
    __tablename__ = "soggetti"
    
    id = Column(Integer, primary_key=True, index=True)
    codice_fiscale = Column(String(16), index=True, nullable=True)
    nominativo = Column(Text, index=True)
    valido_dal = Column(DateTime, default=datetime.utcnow)
    
    titolarita = relationship("Titolarita", back_populates="soggetto")

class Titolarita(Base):
    __tablename__ = "titolarita"
    
    id = Column(Integer, primary_key=True, index=True)
    immobile_id = Column(Integer, ForeignKey("immobili.id"))
    soggetto_id = Column(Integer, ForeignKey("soggetti.id"))
    
    tipo_titolarita = Column(String(255), nullable=True)
    quota = Column(String(100), nullable=True)
    regime = Column(String(255), nullable=True)
    
    immobile = relationship("Immobile", back_populates="titolarita")
    soggetto = relationship("Soggetto", back_populates="titolarita")

class CatalogComune(Base):
    __tablename__ = "catalog_comuni"
    
    codice_catastale = Column(String(10), primary_key=True, index=True)
    denominazione = Column(String(255), index=True)
    sigla_provincia = Column(String(5), index=True)
    regione = Column(String(100), index=True)
    codice_istat = Column(String(10), index=True)
    
    # Upstream Overrides for provider compatibility
    denominazione_upstream = Column(String(255), nullable=True)
    provincia_upstream = Column(String(255), nullable=True)
    regione_upstream = Column(String(1055), nullable=True)

class CatalogParcel(Base):
    __tablename__ = "catalog_parcels"
    
    id = Column(Integer, primary_key=True, index=True)
    codice_comune = Column(String(10), index=True)
    sezione = Column(String(10), index=True, nullable=True)
    foglio = Column(String(10), index=True)
    particella = Column(String(10), index=True)
    
    # We'll use a unique constraint to support UPSERT/Merge
    from sqlalchemy import UniqueConstraint
    __table_args__ = (
        UniqueConstraint('codice_comune', 'sezione', 'foglio', 'particella', name='_parcel_uc'),
    )

class QueryCache(Base):
    __tablename__ = "query_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    params_hash = Column(String(64), unique=True, index=True)
    status = Column(String(20), index=True) # 'processing', 'completed', 'error'
    upstream_id = Column(String(255), nullable=True, index=True)
    params = Column(JSON, nullable=True) # Original request parameters for normalization
    results_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
