import time
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean as Bool, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "postgresql://pizza:pizza@db:5432/pizza_db"

for i in range(10):
    try:
        engine = create_engine(DATABASE_URL)
        engine.connect()
        print("DB connected!")
        break
    except Exception:
        print("DB not ready, retrying...")
        time.sleep(2)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class PizzaData(Base):
    __tablename__ = "pizza_data"

    id = Column(Integer, primary_key=True)
    success = Column(Bool)
    pizza_type = Column(String)
    confidence = Column(Float)
    status = Column(String)
    reason = Column(String)
    ingredients_found = Column(JSON)


Base.metadata.create_all(engine)


def save_to_db(result):
    db = SessionLocal()

    record = PizzaData(
        success=result.get("success"),
        pizza_type=result.get("pizza_type"),
        confidence=result.get("confidence"),
        status=result.get("status"),
        reason=result.get("reason"),
        ingredients_found=result.get("ingredients_found")
    )

    db.add(record)
    db.commit()
    db.close()
