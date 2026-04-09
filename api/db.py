import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean as Bool, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

engine = None
SessionLocal = None


def init_db():
    global engine, SessionLocal

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://pizza:pizza@db:5432/pizza_db"
    )

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)

    
    if "sqlite" not in DATABASE_URL:
        Base.metadata.create_all(engine)


class PizzaData(Base):
    __tablename__ = "pizza_data"

    id = Column(Integer, primary_key=True)

    success = Column(Bool)
    report = Column(String)
    pizzas = Column(JSON)

    chat_id = Column(String)
    feedback = Column(String)
    image = Column(String)


def save_to_db(result, image_base64, db=None):
    if db is None:
        if SessionLocal is None:
            raise RuntimeError("DB is not initialized. Call init_db()")

        db = SessionLocal()
        close = True
    else:
        close = False

    record = PizzaData(
        success=result.get("success"),
        report=result.get("report"),
        pizzas=result.get("pizzas"),
        chat_id=result.get("chat_id"),
        image=image_base64
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    if close:
        db.close()

    return record.id