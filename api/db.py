import time
from sqlalchemy import create_engine, Column, Integer, String, Boolean as Bool, JSON
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
    report = Column(String)
    pizzas = Column(JSON)

    chat_id = Column(String)
    feedback = Column(String)

    image = Column(String)


Base.metadata.create_all(engine)


def save_to_db(result, image_base64):
    db = SessionLocal()

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

    record_id = record.id

    db.close()
    return record_id