import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3
import os
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен бота (в продакшене использовать переменные окружения)
BOT_TOKEN = os.getenv('BOT_TOKEN', '8581156425:AAEgM1gBOVO28lrhTC8RMQuEOszm9qnJgR0')

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для FSM
class TaskStates(StatesGroup):
    waiting_for_answer = State()

# Подключение к базе данных заданий
def get_db_connection():
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # Таблица заданий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            solution TEXT,
            topic TEXT
        )
    ''')
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица прогресса
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            is_correct INTEGER,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # Проверяем, есть ли уже задания
    cursor.execute('SELECT COUNT(*) FROM tasks')
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Добавляем 10 заданий
        tasks = [
            (1, "Найдите значение выражения: 3,7 - 2,4", "1.3", "3,7 - 2,4 = 1,3", "Арифметика"),
            (2, "В таблице даны результаты забега мальчиков. Какое место занял Петя?\n\nИгорь - 12.3с\nПетя - 11.9с\nВася - 12.1с", "1", "Петя пробежал быстрее всех (11.9с), значит занял 1 место", "Таблицы"),
            (3, "На координатной прямой отмечены числа a и b. Какое из следующих чисел наибольшее?\nПусть a = -2, b = 3\n1) a+b  2) 2a  3) -b  4) a-b", "1", "a+b = -2+3 = 1\n2a = -4\n-b = -3\na-b = -5\nНаибольшее: 1", "Координатная прямая"),
            (4, "Решите уравнение: x² = 49", "7", "x² = 49\nx = ±√49\nx = ±7\nПо условиям ОГЭ обычно берем положительный корень: x = 7", "Уравнения"),
            (5, "На рисунке показан график изменения температуры. Сколько часов температура была выше 0°C?\n(График показывает: с 6:00 до 18:00 температура была положительной)", "12", "С 6 утра до 18 вечера = 12 часов", "Графики"),
            (6, "Найдите значение выражения: (2/3 + 1/6) × 12", "10", "(2/3 + 1/6) = 4/6 + 1/6 = 5/6\n5/6 × 12 = 10", "Дроби"),
            (7, "Какая из точек принадлежит прямой y = 2x + 1?\n1) (0;1)  2) (1;2)  3) (2;5)  4) (3;6)", "3", "Подставляем координаты:\n(2;5): y = 2×2 + 1 = 5 ✓", "Функции"),
            (8, "Упростите выражение: (x-3)(x+3)", "x²-9", "(x-3)(x+3) = x² - 9 (формула разности квадратов)", "Алгебра"),
            (9, "В треугольнике ABC угол C = 90°, AB = 10, AC = 6. Найдите BC.", "8", "По теореме Пифагора: BC² = AB² - AC²\nBC² = 100 - 36 = 64\nBC = 8", "Геометрия"),
            (10, "Вероятность того, что новая ручка пишет плохо, равна 0,02. Покупатель покупает одну ручку. Найдите вероятность того, что ручка пишет хорошо.", "0.98", "P(хорошо) = 1 - P(плохо) = 1 - 0,02 = 0,98", "Вероятность")
        ]
        
        cursor.executemany('''
            INSERT INTO tasks (number, question, answer, solution, topic)
            VALUES (?, ?, ?, ?, ?)
        ''', tasks)
        
        conn.commit()
        logging.info("База данных инициализирована с 10 заданиями")
    
    conn.close()

# Функция регистрации пользователя
async def register_user(user_id, username, first_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    conn.commit()
    conn.close()

# Главное меню
def get_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Решить задание", callback_data="solve_task")],
        [InlineKeyboardButton(text="🎲 Случайное задание", callback_data="random_task")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    return keyboard

# Меню выбора номера задания
def get_task_numbers_menu():
    buttons = []
    row = []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"task_{i}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Обработчик команды /start
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я бот для подготовки к ОГЭ по математике.\n\n"
        "📚 У меня есть задания из разных тем:\n"
        "• Арифметика\n"
        "• Алгебра\n"
        "• Геометрия\n"
        "• Графики и функции\n"
        "• И другие\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu()
    )

# Обработчик команды /menu
@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("📋 Главное меню:", reply_markup=get_main_menu())

# Обработчик кнопки "Решить задание"
@dp.callback_query(F.data == "solve_task")
async def process_solve_task(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выбери номер задания (1-10):",
        reply_markup=get_task_numbers_menu()
    )
    await callback.answer()

# Обработчик кнопки "Случайное задание"
@dp.callback_query(F.data == "random_task")
async def process_random_task(callback: CallbackQuery, state: FSMContext):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks ORDER BY RANDOM() LIMIT 1')
    task = cursor.fetchone()
    conn.close()
    
    if task:
        await state.update_data(current_task_id=task['id'], task_answer=task['answer'])
        await state.set_state(TaskStates.waiting_for_answer)
        
        await callback.message.edit_text(
            f"📝 Задание #{task['number']} ({task['topic']})\n\n"
            f"{task['question']}\n\n"
            "Введите ваш ответ:"
        )
    await callback.answer()

# Обработчик выбора конкретного задания
@dp.callback_query(F.data.startswith("task_"))
async def process_task_selection(callback: CallbackQuery, state: FSMContext):
    task_number = int(callback.data.split("_")[1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE number = ?', (task_number,))
    task = cursor.fetchone()
    conn.close()
    
    if task:
        await state.update_data(current_task_id=task['id'], task_answer=task['answer'])
        await state.set_state(TaskStates.waiting_for_answer)
        
        await callback.message.edit_text(
            f"📝 Задание #{task['number']} ({task['topic']})\n\n"
            f"{task['question']}\n\n"
            "Введите ваш ответ:"
        )
    await callback.answer()

# Обработчик ответа на задание
@dp.message(TaskStates.waiting_for_answer)
async def process_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('current_task_id')
    correct_answer = data.get('task_answer')
    user_answer = message.text.strip().replace(',', '.')
    
    # Получаем информацию о задании
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    
    # Проверяем ответ
    is_correct = user_answer.lower() == correct_answer.lower()
    
    # Сохраняем результат
    cursor.execute('''
        INSERT INTO user_progress (user_id, task_id, is_correct)
        VALUES (?, ?, ?)
    ''', (message.from_user.id, task_id, int(is_correct)))
    conn.commit()
    conn.close()
    
    if is_correct:
        response = (
            "✅ Правильно!\n\n"
            f"📖 Решение:\n{task['solution']}"
        )
    else:
        response = (
            f"❌ Неправильно.\n\n"
            f"Правильный ответ: {correct_answer}\n\n"
            f"📖 Решение:\n{task['solution']}"
        )
    
    await message.answer(response, reply_markup=get_main_menu())
    await state.clear()

# Обработчик статистики
@dp.callback_query(F.data == "stats")
async def process_stats(callback: CallbackQuery):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(is_correct) as correct
        FROM user_progress
        WHERE user_id = ?
    ''', (callback.from_user.id,))
    
    stats = cursor.fetchone()
    conn.close()
    
    total = stats['total'] if stats else 0
    correct = stats['correct'] if stats and stats['correct'] else 0
    
    if total > 0:
        percentage = (correct / total) * 100
        text = (
            f"📊 Ваша статистика:\n\n"
            f"Всего решено заданий: {total}\n"
            f"Правильных ответов: {correct}\n"
            f"Неправильных ответов: {total - correct}\n"
            f"Процент правильных: {percentage:.1f}%"
        )
    else:
        text = "📊 Вы еще не решали заданий.\nНачните прямо сейчас!"
    
    await callback.message.edit_text(text, reply_markup=get_main_menu())
    await callback.answer()

# Обработчик помощи
@dp.callback_query(F.data == "help")
async def process_help(callback: CallbackQuery):
    help_text = (
        "ℹ️ Как пользоватьсяботом:\n\n"
        "1️⃣ Нажми 'Решить задание' и выбери номер (1-10)\n"
        "2️⃣ Или выбери 'Случайное задание'\n"
        "3️⃣ Реши задачу и введи ответ\n"
        "4️⃣ Получи проверку и разбор решения\n"
        "5️⃣ Смотри свою статистику\n\n"
        "💡 Советы:\n"
        "• Используй точку для десятичных дробей\n"
        "• Внимательно читай условие\n"
        "• Не бойся ошибаться - это часть обучения!\n\n"
        "Команды:\n"
        "/start - начать заново\n"
        "/menu - главное меню"
    )
    await callback.message.edit_text(help_text, reply_markup=get_main_menu())
    await callback.answer()

# Обработчик кнопки "Назад"
@dp.callback_query(F.data == "back_to_menu")
async def process_back(callback: CallbackQuery):
    await callback.message.edit_text("📋 Главное меню:", reply_markup=get_main_menu())
    await callback.answer()

# Запуск бота
async def main():
    init_db()
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())