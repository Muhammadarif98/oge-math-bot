import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3
import os

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8581156425:AAEgM1gBOVO28lrhTC8RMQuEOszm9qnJgR0")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class TaskStates(StatesGroup):
    waiting_for_answer = State()


# --- DATABASE --- #
def get_db_connection():
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = sqlite3.connect("tasks.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            solution TEXT,
            topic TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            is_correct INTEGER,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM tasks")
    count = cursor.fetchone()[0]

    if count == 0:
        tasks = [
            # Арифметика
            (1, "Найдите значение выражения: 3,7 - 2,4", "1.3", "3,7 - 2,4 = 1,3", "Арифметика"),
            (2, "Найдите значение выражения: 4² + 3²", "25", "4² + 3² = 16 + 9 = 25", "Арифметика"),
            (3, "Сколько процентов составляет число 20 от 80?", "25", "20/80×100% = 25%", "Арифметика"),
            (4, "Найдите значение выражения: (2/3 + 1/6) × 12", "10", "(2/3 + 1/6)=5/6; 5/6×12=10", "Арифметика"),
            (5, "Сколько граммов соли содержится в 200 г раствора с концентрацией 15%?", "30", "200×0,15=30 г", "Арифметика"),

            # Алгебра
            (6, "Решите уравнение: x² = 49", "7", "x²=49 ⇒ x=±7 ⇒ x=7", "Алгебра"),
            (7, "Решите уравнение: 5x - 10 = 0", "2", "5x=10 ⇒ x=2", "Алгебра"),
            (8, "Упростите выражение: (x-3)(x+3)", "x²-9", "(x-3)(x+3)=x²-9", "Алгебра"),
            (9, "Решите уравнение: 2x + 6 = 0", "-3", "2x=-6 ⇒ x=-3", "Алгебра"),
            (10, "Найдите корень уравнения: 3x = 12", "4", "3x=12 ⇒ x=4", "Алгебра"),

            # Геометрия
            (11, "Периметр квадрата равен 24. Найдите его сторону.", "6", "P=4a ⇒ 24=4a ⇒ a=6", "Геометрия"),
            (12, "Площадь прямоугольника равна 24, одна сторона 4. Найдите другую.", "6", "S=ab ⇒ 24=4b ⇒ b=6", "Геометрия"),
            (13, "В треугольнике ABC угол C=90°, AB=10, AC=6. Найдите BC.", "8", "BC²=AB²-AC² ⇒ 64 ⇒ BC=8", "Геометрия"),
            (14, "Радиус круга 7 см. Найдите длину окружности (π=3.14)", "43.96", "L=2πr=2×3.14×7=43.96", "Геометрия"),
            (15, "Сторона квадрата 5 см. Найдите его площадь.", "25", "S=a²=25", "Геометрия"),

            # Графики и функции
            (16, "Какая из точек принадлежит прямой y = 2x + 1?\n1) (0;1) 2) (1;2) 3) (2;5) 4) (3;6)", "3", "(2;5): y=2×2+1=5 ✓", "Функции"),
            (17, "На графике y = 3x - 2. Найдите y при x = 4.", "10", "y=3×4-2=10", "Функции"),
            (18, "Функция y = 5 - x. Найдите y при x = 2.", "3", "y=5-2=3", "Функции"),
            (19, "Определите, возрастающая ли функция y = 2x - 3.", "Да", "Коэффициент 2 > 0 ⇒ функция возрастает", "Функции"),
            (20, "При x = 0 функция y = -3x + 4 равна?", "4", "y=-3×0+4=4", "Функции"),

            # Вероятность и статистика
            (21, "Вероятность того, что ручка пишет плохо, 0.02. Найдите вероятность, что пишет хорошо.", "0.98", "1-0.02=0.98", "Вероятность"),
            (22, "Монету бросают 1 раз. Найдите вероятность выпадения орла.", "0.5", "1/2=0.5", "Вероятность"),
            (23, "Кубик бросают. Вероятность выпадения числа больше 4?", "1/3", "2 из 6 ⇒ 2/6=1/3", "Вероятность"),
            (24, "В мешке 5 белых и 3 черных шара. Вероятность вытащить белый?", "0.625", "5/8=0.625", "Вероятность"),
            (25, "Карточку с номером от 1 до 10. Вероятность, что номер четный?", "0.5", "5/10=0.5", "Вероятность"),

            # Таблицы и анализ данных
            (26, "Петя пробежал 11.9с, Вася — 12.1с, Игорь — 12.3с. Какое место занял Петя?", "1", "Самое меньшее время ⇒ 1 место", "Таблицы"),
            (27, "Средняя температура за 3 дня: 10, 12, 14. Найдите среднюю.", "12", "(10+12+14)/3=12", "Таблицы"),
            (28, "В таблице продажи: 20, 25, 30, 25. Мода?", "25", "Наиболее частое значение = 25", "Таблицы"),
            (29, "Медиана чисел 3, 7, 9?", "7", "Среднее значение = 7", "Таблицы"),
            (30, "Среднее арифметическое 4 и 10?", "7", "(4+10)/2=7", "Таблицы"),
        ]
        cursor.executemany("INSERT INTO tasks (number, question, answer, solution, topic) VALUES (?, ?, ?, ?, ?)", tasks)
        conn.commit()
        logging.info("✅ База данных инициализирована с 30 заданиями.")
    conn.close()


# --- MENU --- #
def get_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Решить задание", callback_data="solve_task")],
        [InlineKeyboardButton(text="📚 Выбрать тему", callback_data="choose_topic")],
        [InlineKeyboardButton(text="🎲 Случайное задание", callback_data="random_task")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    return keyboard


def get_task_numbers_menu():
    buttons, row = [], []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"task_{i}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_topic_menu():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT topic FROM tasks ORDER BY topic")
    topics = [row["topic"] for row in cursor.fetchall()]
    conn.close()
    buttons = [[InlineKeyboardButton(text=topic, callback_data=f"topic_{topic}")] for topic in topics]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- COMMANDS --- #
async def register_user(user_id, username, first_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", (user_id, username, first_name))
    conn.commit()
    conn.close()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я помогу тебе подготовиться к 🧮 <b>ОГЭ по математике</b>!\n\n"
        "Выбери, что хочешь сделать:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("📋 Главное меню:", reply_markup=get_main_menu())


# --- CALLBACK HANDLERS --- #
@dp.callback_query(F.data == "solve_task")
async def process_solve_task(callback: CallbackQuery):
    await callback.message.edit_text("Выбери номер задания (1-10):", reply_markup=get_task_numbers_menu())
    await callback.answer()


@dp.callback_query(F.data == "choose_topic")
async def process_choose_topic(callback: CallbackQuery):
    await callback.message.edit_text("📘 Выбери тему:", reply_markup=get_topic_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("topic_"))
async def process_topic(callback: CallbackQuery, state: FSMContext):
    topic = callback.data.replace("topic_", "")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE topic=? ORDER BY RANDOM() LIMIT 1", (topic,))
    task = cursor.fetchone()
    conn.close()

    if not task:
        await callback.message.edit_text(f"❌ В теме <b>{topic}</b> пока нет заданий.", parse_mode="HTML", reply_markup=get_main_menu())
        return

    await state.update_data(current_task_id=task["id"], task_answer=task["answer"])
    await state.set_state(TaskStates.waiting_for_answer)
    await callback.message.edit_text(
        f"📘 Тема: <b>{task['topic']}</b>\n\n"
        f"📝 Задание №{task['number']}\n\n"
        f"{task['question']}\n\n"
        "<b>Введите ваш ответ:</b>",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "random_task")
async def process_random_task(callback: CallbackQuery, state: FSMContext):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY RANDOM() LIMIT 1")
    task = cursor.fetchone()
    conn.close()

    if task:
        await state.update_data(current_task_id=task["id"], task_answer=task["answer"])
        await state.set_state(TaskStates.waiting_for_answer)
        await callback.message.edit_text(
            f"📝 Задание №{task['number']} ({task['topic']})\n\n"
            f"{task['question']}\n\n"
            "Введите ваш ответ:"
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("task_"))
async def process_task_selection(callback: CallbackQuery, state: FSMContext):
    task_number = int(callback.data.split("_")[1])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE number=?", (task_number,))
    task = cursor.fetchone()
    conn.close()

    if task:
        await state.update_data(current_task_id=task["id"], task_answer=task["answer"])
        await state.set_state(TaskStates.waiting_for_answer)
        await callback.message.edit_text(
            f"📝 Задание №{task['number']} ({task['topic']})\n\n"
            f"{task['question']}\n\n"
            "Введите ваш ответ:"
        )
    await callback.answer()


# --- ANSWER HANDLER --- #
@dp.message(TaskStates.waiting_for_answer)
async def process_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("current_task_id")
    correct_answer = data.get("task_answer")
    user_answer = message.text.strip().replace(",", ".")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    task = cursor.fetchone()

    is_correct = user_answer.lower() == correct_answer.lower()
    cursor.execute("INSERT INTO user_progress (user_id, task_id, is_correct) VALUES (?, ?, ?)",
                   (message.from_user.id, task_id, int(is_correct)))
    conn.commit()
    conn.close()

    if is_correct:
        response = f"✅ <b>Правильно!</b>\n\n📖 Решение:\n{task['solution']}"
    else:
        response = f"❌ <b>Неправильно.</b>\n\nПравильный ответ: <b>{correct_answer}</b>\n\n📖 Решение:\n{task['solution']}"

    await message.answer(response, parse_mode="HTML", reply_markup=get_main_menu())
    await state.clear()


# --- STATS --- #
@dp.callback_query(F.data == "stats")
async def process_stats(callback: CallbackQuery):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(is_correct) FROM user_progress WHERE user_id=?", (callback.from_user.id,))
    total, correct = cursor.fetchone()
    conn.close()

    correct = correct or 0
    if total:
        percent = (correct / total) * 100
        text = f"📊 Ваша статистика:\n\nВсего решено: {total}\nПравильных: {correct}\nОшибок: {total - correct}\nПроцент: {percent:.1f}%"
    else:
        text = "📊 Вы ещё не решали заданий. Начните прямо сейчас!"
    await callback.message.edit_text(text, reply_markup=get_main_menu())
    await callback.answer()


# --- HELP --- #
@dp.callback_query(F.data == "help")
async def process_help(callback: CallbackQuery):
    text = (
        "ℹ️ Как пользоваться ботом:\n\n"
        "1️⃣ Нажми «📝 Решить задание» или «📚 Выбрать тему»\n"
        "2️⃣ Введи ответ\n"
        "3️⃣ Получи проверку и разбор решения\n"
        "4️⃣ Смотри свою статистику 📊\n\n"
        "Команды:\n/start — начать\n/menu — меню"
    )
    await callback.message.edit_text(text, reply_markup=get_main_menu())
    await callback.answer()


@dp.callback_query(F.data == "back_to_menu")
async def process_back(callback: CallbackQuery):
    await callback.message.edit_text("📋 Главное меню:", reply_markup=get_main_menu())
    await callback.answer()


async def main():
    init_db()
    logging.info("🤖 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
