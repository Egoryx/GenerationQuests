import streamlit as st
import json
import re
from openai import OpenAI

# --- Функции для логики квеста ---

def create_llm_prompt(genre: str, hero: str, goal: str) -> str:
    """
    Окончательная, наиболее надежная версия запроса для максимальной надежности.
    """
    prompt = f"""
Ты — талантливый сценарист, который создаёт глубокие и нелинейные квесты для RPG в формате JSON.

ЗАДАЧА:
Создай квест на русском языке по следующим параметрам:
- Жанр: '{genre}'
- Главный герой: '{hero}'
- Основная цель: '{goal}'

Твой ответ должен быть единым, синтаксически правильным JSON-массивом и больше ничем.

КЛЮЧЕВЫЕ ТРЕБОВАНИЯ К JSON-СТРУКТУРЕ:
1.  **Длина и глубина:** Квест должен быть большим и проработанным. **Общее количество сцен должно быть не менее 8**. Важно: все пути от начала до любой из концовок должны быть глубокими. **Минимальная длина любой сюжетной ветки — 5 сцен.** Не создавай коротких тупиковых веток.
2.  **Формат:** Весь квест — это один JSON-массив `[]`, содержащий объекты сцен. Ответ должен начинаться с `[` и заканчиваться `]`.
3.  **Локация:** В каждой сцене обязательно должно быть поле `"location"` с кратким описанием места действия (например, "Неоновая улица", "Древние руины").
4.  **Выбор:** В каждой сцене должно быть поле `"choices"` с массивом **от 2 до 4 вариантов выбора**. Старайся варьировать количество выборов, чтобы сделать квест более интересным и непредсказуемым.

ПРИМЕР СТРУКТУРЫ СЦЕНЫ:
{{
    "scene_id": "уникальный_идентификатор",
    "location": "описание_места_действия",
    "text": "основной_текст_сцены",
    "choices": [
        {{ "text": "текст_выбора_1", "next_scene": "id_сцены_1" }},
        {{ "text": "текст_выбора_2", "next_scene": "id_сцены_2" }}
    ]
}}

ЧЕГО СЛЕДУЕТ ИЗБЕГАТЬ (ВАЖНО!):
- **Никакого постороннего текста:** Не пиши "Вот ваш JSON:" или любые другие слова вне самого JSON.
- **Только двойные кавычки:** Все ключи и строковые значения должны быть в двойных кавычках (`"`). Одинарные кавычки (`'`) запрещены.
- **Никаких висячих запятых:** Не ставь запятую после последнего элемента в массиве или объекте.

Начинай квест со сцены с `"scene_id": "start"`.
"""
    return prompt

def generate_quest_with_caila(prompt: str) -> str:
    """
    Отправляет запрос на вашу конечную точку API и возвращает сгенерированный квест..
    """
    try:
        api_key = st.session_state.get("api_key")
        if not api_key:
            return '{"error": "API ключ не был предоставлен."}'

        client = OpenAI(
            api_key=api_key,
            base_url="https://caila.io/api/adapters/openai"
        )

        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="just-ai/gigachat/GigaChat-2-Max",
            temperature=0.75
        )

        content = completion.choices[0].message.content
        
        match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
        if match:
            return match.group(1).strip()

        first_brace = content.find('{')
        first_bracket = content.find('[')
        start_index = -1

        if first_brace == -1 and first_bracket != -1:
            start_index = first_bracket
        elif first_bracket == -1 and first_brace != -1:
            start_index = first_brace
        elif first_brace != -1 and first_bracket != -1:
            start_index = min(first_brace, first_bracket)

        if start_index != -1:
            last_brace = content.rfind('}')
            last_bracket = content.rfind(']')
            end_index = max(last_brace, last_bracket)
            if end_index > start_index:
                return content[start_index : end_index + 1].strip()
        
        return content.strip()

    except Exception as e:
        return f'{{"error": "Произошла ошибка при вызове API", "details": "{str(e)}"}}'

# --- НОВАЯ ФУНКЦИЯ ВАЛИДАЦИИ ---
def validate_quest_logic(quest_data: list) -> list:
    """
    Проверяет логическую целостность квеста (наличие 'start', 'битые' ссылки и т.д.).
    Возвращает список найденных текстовых ошибок.
    """
    errors = []
    # Собираем все существующие ID сцен
    scene_ids = {scene.get("scene_id") for scene in quest_data if scene.get("scene_id")}
    
    if not scene_ids:
        errors.append("Квест не содержит ни одной сцены с 'scene_id'.")
        return errors # Дальше проверять бессмысленно

    # 1. Проверка наличия стартовой сцены
    if "start" not in scene_ids:
        errors.append("В квесте отсутствует обязательная стартовая сцена с 'scene_id': 'start'.")

    referenced_ids = set()
    
    for i, scene in enumerate(quest_data):
        scene_id = scene.get("scene_id")
        if not scene_id:
            errors.append(f"Сцена #{i+1} (без ID) не имеет 'scene_id'.")
            continue

        # 2. Проверка, что каждый выбор ведет в существующую сцену
        choices = scene.get("choices", [])
        for choice_num, choice in enumerate(choices):
            next_scene = choice.get("next_scene")
            if not next_scene:
                errors.append(f"В сцене '{scene_id}' у выбора #{choice_num+1} отсутствует поле 'next_scene'.")
            elif next_scene not in scene_ids:
                errors.append(f"В сцене '{scene_id}' есть выбор, который ссылается на несуществующую сцену '{next_scene}'.")
            referenced_ids.add(next_scene)

    # 3. Проверка на наличие "изолированных" сцен, на которые нельзя попасть
    unreachable_scenes = scene_ids - referenced_ids - {"start"}
    if unreachable_scenes:
        errors.append(f"Найдены изолированные сцены, на которые нет переходов: {', '.join(unreachable_scenes)}.")
        
    return errors

# --- Основной веб-интерфейс Streamlit ---

st.set_page_config(page_title="Генератор Квестов", page_icon="📜", layout="centered")
st.title("📜 Генератор Квестов для RPG")
st.write("Этот инструмент использует ИИ для создания уникальных квестов на основе ваших идей.")

api_key = st.text_input("Введите ваш API ключ от caila.io", type="password", help="Ваш ключ не сохраняется и используется только для этого сеанса.")
st.session_state["api_key"] = api_key

st.header("1. Опишите вашу идею")
genre = st.text_input("Жанр", placeholder="Например, фэнтези, киберпанк, нуар...")
hero = st.text_input("Главный герой", placeholder="Например, эльфийский следопыт, хакер-одиночка...")
goal = st.text_input("Цель квеста", placeholder="Например, найти украденный артефакт, взломать сервер...")

st.header("2. Запустите генерацию")
if st.button("✨ Сгенерировать квест!"):
    # Сбрасываем состояние от предыдущих квестов
    for key in ['quest_data', 'current_scene_id', 'quest_scenes_dict']:
        if key in st.session_state:
            del st.session_state[key]

    if not all([genre, hero, goal, st.session_state.get("api_key")]):
        st.warning("Пожалуйста, заполните все поля и введите API ключ.")
    else:
        with st.spinner("Магия в действии... Модель пишет вашу историю..."):
            final_prompt = create_llm_prompt(genre, hero, goal)
            json_response = generate_quest_with_caila(final_prompt)
            
            try:
                quest_data = json.loads(json_response)
                
                # Приводим данные к единому формату (список сцен)
                processed_quest_data = []
                if isinstance(quest_data, dict):
                    if "error" in quest_data:
                        st.error(f"**Ошибка API:** {quest_data.get('details', 'Неизвестная ошибка')}")
                        st.stop()
                    else:
                        processed_quest_data = list(quest_data.values())
                else:
                    processed_quest_data = quest_data
                
                # --- ВНЕДРЕНИЕ ВАЛИДАЦИИ ---
                validation_errors = validate_quest_logic(processed_quest_data)
                
                if validation_errors:
                    st.error("**Внимание! Модель сгенерировала квест с логическими ошибками:**")
                    for error in validation_errors:
                        st.warning(f"- {error}")
                    st.info("Вы можете скачать JSON ниже и исправить его вручную, или попробовать сгенерировать квест заново.")
                    # Сохраняем "сломанный" квест, чтобы его можно было скачать и изучить
                    st.session_state['quest_data_broken'] = processed_quest_data

                else:
                    # Если ошибок нет, сохраняем квест для интерпретации
                    st.session_state['quest_data'] = processed_quest_data
                    
                    # --- ОПТИМИЗАЦИЯ: Создаем словарь сцен один раз и сохраняем ---
                    st.session_state['quest_scenes_dict'] = {scene["scene_id"]: scene for scene in processed_quest_data}
                    st.session_state['current_scene_id'] = 'start'
                    st.success("Квест успешно сгенерирован и прошел логическую проверку!")

            except json.JSONDecodeError:
                st.error("Критическая ошибка: Модель вернула ответ в неверном формате, который не удалось исправить автоматически.")
                st.code(json_response, language="text")

# --- Блок для отображения и прохождения квеста ---

# Проверяем, есть ли валидный квест для прохождения
if 'quest_data' in st.session_state:
    st.header("3. Ваш готовый квест")
    st.download_button(
       label="📥 Скачать quest.json",
       data=json.dumps(st.session_state['quest_data'], indent=4, ensure_ascii=False).encode('utf-8'),
       file_name="quest.json",
       mime="application/json"
    )

    st.header("4. Интерпретация квеста")
    
    # Получаем готовый словарь из состояния
    quest_scenes = st.session_state.get('quest_scenes_dict', {})
    current_scene_id = st.session_state.get('current_scene_id', 'start')

    if current_scene_id in quest_scenes:
        current_scene = quest_scenes[current_scene_id]

        st.info(f"📍 **Локация:** {current_scene.get('location', 'Неизвестно')}")

        with st.chat_message("user", avatar="📜"):
            st.write(current_scene['text'])

        st.write("---")
        st.subheader("Выберите ваше действие:")

        if current_scene.get('choices'):
            cols = st.columns(len(current_scene['choices']))
            for i, choice in enumerate(current_scene['choices']):
                if cols[i].button(choice['text'], key=f"{current_scene_id}_{i}"):
                    st.session_state['current_scene_id'] = choice['next_scene']
                    st.rerun()
        else:
            st.success("🎉 Это одна из возможных концовок квеста! 🎉")

    else:
        st.success("🎉 Квест завершен! 🎉")
        if st.button("Начать заново"):
            st.session_state['current_scene_id'] = 'start'
            st.rerun()

# Блок для отображения "сломанного" квеста, чтобы его можно было скачать
elif 'quest_data_broken' in st.session_state:
     st.header("3. Сгенерированный квест (с ошибками)")
     st.download_button(
       label="📥 Скачать некорректный quest.json",
       data=json.dumps(st.session_state['quest_data_broken'], indent=4, ensure_ascii=False).encode('utf-8'),
       file_name="quest_with_errors.json",
       mime="application/json"
    )
     st.json(st.session_state['quest_data_broken'])
