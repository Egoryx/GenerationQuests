import os
import json
import re
from openai import OpenAI

def parse_input_file(filepath: str) -> tuple[str, str, str]:
    """
    Читает входной TXT-файл и извлекает из него жанр, главного героя и цель.
    """
    print(f"Читаем входной файл: {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            genre = lines[0].strip().replace('Жанр:', '').strip()
            hero = lines[1].strip().replace('Главный герой:', '').strip()
            goal = lines[2].strip().replace('Цель:', '').strip()
            print(f"Успешно прочитаны данные: Жанр='{genre}', Герой='{hero}', Цель='{goal}'")
            return genre, hero, goal
    except (FileNotFoundError, IndexError):
        print(f"Ошибка: Файл {filepath} не найден или имеет неверный формат.")
        return None, None, None


def create_llm_prompt(genre: str, hero: str, goal: str) -> str:
    """
    Формирует подробный промпт для языковой модели на основе входных данных.
    """
    # Инструкции для модели
    prompt = f"""
Создай квест на русском языке для RPG в жанре '{genre}'.
Главный герой: {hero}.
Основная цель квеста: {goal}.

Требования к квесту:
1.  Квест должен содержать от 5 до 10 сцен.
2.  В квесте должна быть как минимум одна развилка, ведущая к разным последствиям. Глубина этой побочной ветки должна быть не менее 3 сцен.
3.  Каждая сцена должна предлагать игроку минимум 2 варианта выбора.
4.  Твой ответ должен быть СТРОГО в формате JSON. Не добавляй никакого текста, объяснений или комментариев до или после JSON-объекта.

Структура JSON для каждой сцены должна быть следующей:
{{
    "scene_id": "уникальный_идентификатор_сцены",
    "text": "основной текст сцены с описанием ситуации или диалога",
    "choices": [
        {{
            "text": "текст первого выбора",
            "next_scene": "id_следующей_сцены"
        }},
        {{
            "text": "текст второго выбора",
            "next_scene": "id_другой_сцены"
        }}
    ]
}}

Начинай квест со сцены с `scene_id` 'start'. Весь квест должен быть представлен как один JSON-массив, содержащий объекты сцен.
"""
    print("\n--- Сгенерированный промпт для модели ---")
    print(prompt)
    print("-----------------------------------------\n")
    return prompt

def generate_quest_with_caila(prompt: str) -> str:
    """
    Отправляет запрос к вашему эндпоинту API и возвращает сгенерированный квест.
    """
    print("Инициализация клиента и отправка запроса на caila.io...")
    try:

        client = OpenAI(
            api_key="MLP_API_KEY",
            base_url="https://caila.io/api/adapters/openai"
        )

        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="just-ai/claude/claude-sonnet-4",
        )

        # Извлекаем текстовый ответ от модели
        content = completion.choices[0].message.content

        # Очистка ответа от возможных блоков кода
        match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return content.strip()

    except Exception as e:
        print(f"Произошла ошибка при вызове API: {e}")
        return None

def save_quest_to_json(quest_data: list, output_filepath: str):
    """
    Сохраняет данные квеста в JSON-файл.
    """
    print(f"Сохраняем результат в файл: {output_filepath}")
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(quest_data, f, ensure_ascii=False, indent=4)
        print("Файл quest.json успешно создан!")
    except Exception as e:
        print(f"Произошла ошибка при сохранении файла: {e}")

def main():
    """
    Главная функция для запуска всего процесса.
    """
    input_filename = "text.txt"

    output_filename = "quest.json"

    # 1. Чтение входных данных
    genre, hero, goal = parse_input_file(input_filename)
    if not all((genre, hero, goal)):
        return

    # 2. Создание промпта
    prompt = create_llm_prompt(genre, hero, goal)

    # 3. Генерация квеста с помощью API
    generated_json_str = generate_quest_with_caila(prompt)

    if not generated_json_str:
        print("Не удалось получить ответ от модели. Завершение работы.")
        return

    # 4. Сохранение результата
    try:
        quest_data = json.loads(generated_json_str)
        save_quest_to_json(quest_data, output_filename)
    except json.JSONDecodeError:
        print("\n--- Ошибка ---")
        print("Полученный от модели ответ не является валидным JSON.")
        print("Вот что вернула модель:")
        print(generated_json_str)
        print("--------------\n")

if __name__ == "__main__":
    main()