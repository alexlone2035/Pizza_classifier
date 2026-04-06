from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean as Bool
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "postgresql://pizza:pizza@db:5432/pizza_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class PizzaData(Base):
    __tablename__ = "pizza_data"

    id = Column(Integer, primary_key=True)
    quality = Column(String)
    is_pizza_ok = Column(Bool)


Base.metadata.create_all(engine)


def save_to_db(result):
    db = SessionLocal()

    record = PizzaData(
        quality=result["quality"],
        is_pizza_ok=result["is_pizza_ok"]
    )

    db.add(record)
    db.commit()
    db.close()