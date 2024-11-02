from telebot import types
import telebot
import logging
import configparser
from sqlalchemy import create_engine, Column, Integer, BigInteger, Numeric, String, ForeignKey, TIMESTAMP
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import func
import atexit

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('config.ini')
TOKEN = config.get('Token', 'TelegramToken')

db_config = {
    'dbname': config.get('Database', 'dbname'),
    'user': config.get('Database', 'user'),
    'password': config.get('Database', 'password'),
    'host': config.get('Database', 'host'),
    'port': config.get('Database', 'port'),
}

DATABASE_URL = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    balance = Column(Numeric(10, 2), default=0)

class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    platform = Column(String, nullable=False)
    cost = Column(Numeric(10, 2), nullable=False)
    period = Column(String, nullable=False)

class TransactionHistory(Base):
    __tablename__ = 'transaction_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    transaction_type = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

Base.metadata.create_all(engine)

bot = telebot.TeleBot(TOKEN)

commands = [
    types.BotCommand("start", "Начать работу с ботом"),
    types.BotCommand("help", "Помощь"),
    types.BotCommand("add_subscription", "Добавить подписку"),
    types.BotCommand("add_funds", "Пополнить баланс"),
    types.BotCommand("view_balance", "Показать текущий баланс"),
    types.BotCommand("view_subscriptions", "Просмотреть активные подписки"),
    types.BotCommand("transaction_history", "История транзакций"),
]

bot.set_my_commands(commands)

user_states = {}

def add_user(telegram_id):
    user = User(telegram_id=telegram_id)
    session.add(user)
    session.commit()
    return user.id

def get_user(telegram_id):
    return session.query(User).filter_by(telegram_id=telegram_id).first()

def update_balance(user_id, amount):
    user = session.query(User).get(user_id)
    user.balance += amount
    session.commit()
    session.refresh(user)
    return user.balance


def add_subscription(user_id, platform, cost, period):
    subscription = Subscription(user_id=user_id, platform=platform, cost=cost, period=period)
    session.add(subscription)
    session.commit()

def add_transaction(user_id, transaction_type, amount, description):
    transaction = TransactionHistory(user_id=user_id, transaction_type=transaction_type, amount=amount, description=description)
    session.add(transaction)
    session.commit()

def clear_user_state(user_id):
    if user_id in user_states:
        del user_states[user_id]

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_data = get_user(user_id)

    if user_data is None:
        user_id_db = add_user(user_id)
        bot.send_message(message.chat.id, "Добро пожаловать! Вы успешно зарегистрированы.")
    else:
        bot.send_message(message.chat.id, "С возвращением! Вы уже зарегистрированы.")

@bot.message_handler(commands=['add_funds'])
def add_funds(message):
    user_id = message.from_user.id
    user_data = get_user(user_id)

    if user_data is None:
        bot.send_message(message.chat.id, "Сначала зарегистрируйтесь с помощью команды /start.")
        return

    user_states[user_id] = {'step': 'add_funds'}
    bot.send_message(message.chat.id, "Введите сумму пополнения (целое положительное число):")

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id]['step'] == 'add_funds')
def process_funds(message):
    user_id = message.from_user.id
    amount_input = message.text.strip()

    if amount_input.isdigit():
        try:
            amount = float(amount_input)
            if amount <= 0 or not amount.is_integer():
                bot.send_message(message.chat.id, "Пожалуйста, введите положительное целое число для суммы.")
                del user_states[user_id]  # Сброс состояния
                return
            
            if amount > 100000:
                bot.send_message(message.chat.id, "Максимальная сумма пополнения составляет 100000 рублей.")
                del user_states[user_id]  # Сброс состояния
                return

            user_data = get_user(user_id)
            if user_data is None:
                bot.send_message(message.chat.id, "Пользователь не найден. Пожалуйста, зарегистрируйтесь.")
                del user_states[user_id]  # Сброс состояния
                return
            
            new_balance = update_balance(user_data.id, int(amount))
            add_transaction(user_data.id, "пополнение", int(amount), f"Пополнение баланса на {int(amount)} руб.")
            
            bot.send_message(message.chat.id, f"Ваш баланс пополнен на {int(amount)}. Текущий баланс: {new_balance}.")
            del user_states[user_id]
        except ValueError:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректную сумму.")
            del user_states[user_id]  # Сброс состояния при ошибке
    else:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректную сумму.")
        del user_states[user_id]  # Сброс состояния при ошибке

@bot.message_handler(commands=['view_balance'])
def view_balance(message):
    user_id = message.from_user.id
    logger.info(f"Executing /view_balance for user_id: {user_id}")  # Лог для отладки
    
    user_data = get_user(user_id)
    
    if user_data is None:
        bot.send_message(message.chat.id, "Сначала зарегистрируйтесь с помощью команды /start.")
    else:
        bot.send_message(message.chat.id, f"Ваш текущий баланс: {user_data.balance} рублей.")

@bot.message_handler(commands=['add_subscription'])
def add_subscription_command(message):
    user_id = message.from_user.id
    user_data = get_user(user_id)

    if user_data is None:
        bot.send_message(message.chat.id, "Сначала зарегистрируйтесь с помощью команды /start.")
        return

    if user_data.balance <= 0:
        bot.send_message(message.chat.id, "Сначала пополните баланс, чтобы добавить подписку.")
        return

    user_states[user_id] = {'step': 1}
    bot.send_message(message.chat.id, "На какую платформу вы хотите подписаться?")

@bot.message_handler(func=lambda message: message.from_user.id in user_states)
def process_subscription(message):
    user_id = message.from_user.id
    step = user_states[user_id]['step']

    if step == 1:
        user_states[user_id]['platform'] = message.text
        user_states[user_id]['step'] = 2
        bot.send_message(message.chat.id, "Какова сумма подписки?")
    elif step == 2:
        cost_input = message.text.strip()
        if cost_input.isdigit():
            cost = int(cost_input)
            if cost <= 0:
                bot.send_message(message.chat.id, "Пожалуйста, введите положительное целое число для суммы.")
                return
            user_states[user_id]['cost'] = cost
            user_states[user_id]['step'] = 3
            bot.send_message(message.chat.id, "На сколько месяцев вы хотите подписаться? (1-12)")
        else:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректную сумму.")
    elif step == 3:
        period_input = message.text.strip()
        if period_input.isdigit():
            period = int(period_input)
            if 1 <= period <= 12:
                user_states[user_id]['period'] = period

                platform = user_states[user_id]['platform']
                cost = user_states[user_id]['cost']

                user_data = get_user(user_id)
                if user_data.balance < cost:
                    bot.send_message(message.chat.id, "Недостаточно средств для оформления подписки.")
                    del user_states[user_id]
                    return

                add_subscription(user_data.id, platform, cost, f"{period} месяцев")
                update_balance(user_data.id, -cost)
                add_transaction(user_data.id, "подписка", -cost, f"Подписка на {platform} за {cost} рублей на {period} месяцев.")

                bot.send_message(message.chat.id, f"Вы успешно подписались на {platform} за {cost} рублей на {period} месяцев.")
                del user_states[user_id]
            else:
                bot.send_message(message.chat.id, "Пожалуйста, введите количество месяцев от 1 до 12.")
        else:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректное количество месяцев.")

@bot.message_handler(commands=['view_subscriptions'])
def view_subscriptions(message):
    user_id = message.from_user.id
    user_data = get_user(user_id)

    if user_data is None:
        bot.send_message(message.chat.id, "Сначала зарегистрируйтесь с помощью команды /start.")
    else:
        subscriptions = session.query(Subscription).filter_by(user_id=user_data.id).all()
        if subscriptions:
            response = "Ваши активные подписки:\n"
            for sub in subscriptions:
                response += f"- {sub.platform}: {sub.period} за {sub.cost} руб.\n"
            bot.send_message(message.chat.id, response)
        else:
            bot.send_message(message.chat.id, "У вас нет активных подписок.")


@bot.message_handler(commands=['transaction_history'])
def transaction_history(message):
    user_id = message.from_user.id
    user_data = get_user(user_id)

    if user_data is None:
        bot.send_message(message.chat.id, "Сначала зарегистрируйтесь с помощью команды /start.")
        return

    transactions = session.query(TransactionHistory).filter_by(user_id=user_data.id).all()
    if not transactions:
        bot.send_message(message.chat.id, "История транзакций пуста.")
        return

    response = "История транзакций:\n"
    for transaction in transactions:
        response += f"✔️{transaction.created_at}: {transaction.transaction_type} {transaction.amount} рублей - {transaction.description}\n"
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, 
                     "Список доступных команд:\n"
                     "/start - Начать работу с ботом\n"
                     "/add_funds - Пополнить баланс\n"
                     "/add_subscription - Добавить подписку\n"
                     "/view_balance - Показать текущий баланс\n"
                     "/view_subscriptions - Просмотреть активные подписки\n"
                     "/transaction_history - История транзакций")

def cleanup():
    session.close()

atexit.register(cleanup)

if __name__ == "__main__":
    bot.polling(none_stop=True)
