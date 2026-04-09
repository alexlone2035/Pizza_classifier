import pytest
import base64
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.db import Base, PizzaData, save_to_db

TEST_DB_URL = "sqlite:///:memory:"

engine = create_engine(TEST_DB_URL)
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_save_to_db_basic(db):
    result = {
        "success": True,
        "report": "Найдено пицц: 1",
        "pizzas": [
            {"pizza_type": "pepperoni", "confidence": 0.9, "box": [1, 2, 3, 4]}
        ],
        "chat_id": "123"
    }

    image = base64.b64encode(b"test_image").decode()

    record_id = save_to_db(result, image, db=db)

    assert isinstance(record_id, int)


def test_record_saved_correctly(db):
    result = {
        "success": True,
        "report": "Найдено пицц: 2",
        "pizzas": [
            {"pizza_type": "pepperoni", "confidence": 0.9, "box": [1, 2, 3, 4]},
            {"pizza_type": "margarita", "confidence": 0.8, "box": [5, 6, 7, 8]}
        ],
        "chat_id": "456"
    }

    image = base64.b64encode(b"img").decode()

    record_id = save_to_db(result, image, db=db)

    record = db.query(PizzaData).filter(PizzaData.id == record_id).first()

    assert record is not None
    assert record.success is True
    assert record.report == "Найдено пицц: 2"
    assert len(record.pizzas) == 2
    assert record.chat_id == "456"
    assert record.image == image


def test_feedback_update(db):
    result = {
        "success": True,
        "report": "ok",
        "pizzas": [],
        "chat_id": "789"
    }

    image = base64.b64encode(b"img").decode()

    record_id = save_to_db(result, image, db=db)

    record = db.query(PizzaData).filter(PizzaData.id == record_id).first()

    record.feedback = "correct"
    db.commit()

    updated = db.query(PizzaData).filter(PizzaData.id == record_id).first()

    assert updated.feedback == "correct"


def test_multiple_records(db):
    for i in range(5):
        result = {
            "success": True,
            "report": f"test {i}",
            "pizzas": [],
            "chat_id": str(i)
        }

        image = base64.b64encode(f"img{i}".encode()).decode()

        save_to_db(result, image, db=db)

    records = db.query(PizzaData).all()

    assert len(records) == 5


def test_empty_pizzas(db):
    result = {
        "success": True,
        "report": "no pizzas",
        "pizzas": [],
        "chat_id": "000"
    }

    image = base64.b64encode(b"empty").decode()

    record_id = save_to_db(result, image, db=db)

    record = db.query(PizzaData).filter(PizzaData.id == record_id).first()

    assert record.pizzas == []