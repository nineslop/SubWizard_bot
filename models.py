from sqlalchemy import create_engine, Column, Integer, BigInteger, Numeric, String, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

# Создание базового класса для моделей
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)  # Уникальный идентификатор Telegram пользователя
    balance = Column(Numeric(10, 2), default=0)  # Баланс пользователя

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, balance={self.balance})>"

class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Внешний ключ к пользователю
    platform = Column(String, nullable=False)  # Платформа подписки
    cost = Column(Numeric(10, 2), nullable=False)  # Стоимость подписки
    period = Column(String, nullable=False)  # Период подписки (например, "1 месяц")

    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, platform={self.platform}, cost={self.cost}, period={self.period})>"

class TransactionHistory(Base):
    __tablename__ = 'transaction_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Внешний ключ к пользователю
    transaction_type = Column(String, nullable=False)  # Тип транзакции (например, "пополнение", "подписка")
    amount = Column(Numeric(10, 2), nullable=False)  # Сумма транзакции
    description = Column(String, nullable=False)  # Описание транзакции
    created_at = Column(TIMESTAMP, server_default=func.now())  # Время создания записи

    def __repr__(self):
        return f"<TransactionHistory(id={self.id}, user_id={self.user_id}, transaction_type={self.transaction_type}, amount={self.amount}, description={self.description}, created_at={self.created_at})>"
