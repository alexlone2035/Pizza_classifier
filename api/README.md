Database (PostgreSQL)

База данных используется для хранения результатов проверки пиццы, полученных от ML-модели через FastAPI.

Сервис реализован с использованием:

PostgreSQL
SQLAlchemy
Структура таблицы
Таблица: pizza_data
Поле	        |  Тип	       |      Описание
id	          |  Integer	   |      Уникальный ID записи
success	      |  Boolean	   |      Успешность обработки
report	      |  String	     |    Текстовый отчёт
pizzas	      |  JSON	       |    Данные о найденных пиццах
chat_id	      |  String	     |    ID пользователя (Telegram)
feedback	    |  String	     |    Оценка пользователя (correct / wrong)
image	String	|  Изображение |     (base64)
Подключение к базе

Для работы с БД можно использовать любой клиент, например
DBeaver

Параметры подключения
Host: localhost
Port: 5432
Database: значение POSTGRES_DB из .env
User: значение POSTGRES_USER из .env
Password: значение POSTGRES_PASSWORD из .env
