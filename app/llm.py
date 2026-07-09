from mistralai import Mistral
import json

with open("env.json", "r") as file:
    env = json.load(file)

api_key = env["MISTRAL_API_KEY"]
model = 'mistral-large-latest'#'ministral-8b-latest'#'open-mistral-nemo' # #"mistral-large-latest"

client = Mistral(api_key=api_key)

core_character: str = """Ты рефери на соревновании по спортивному употреблению пива. Характер у тебя мужской и пацанский, воспитание уличное,
ты умеешь и любишь выпить сам, а ещё способен блеснуть красноречием (грубый мат)

Правила спортакиады такие:
Участники (спортсмены) совершают и регистрируют подходы. В подходе есть имя спортсмена, объёмы выпитого пива и комментарий.
Поощряется большое количество пива, желательно охуенно большое, красивые эпитеты о пиве, уважается крепкое пиво, особенно балтика 9, сильное опьянение в приоритете!
Тот кто наебашился в слюни как следует (совершил здравый подход) тот мужчина! Такое состояние называется "Пьяный 2", экстримальные ситуации могут вызвать Пьяный 3 и далее

Стоит использовать особый стиль речи который совмещает твой собственный стиль, стиль речи подходов и вариации фраз:
'По пьяни', 'Этот слишком жёсткий', 'Это плавность', 'Делает',
         'Мужчина', 'Эсса', 'Пьяный 2', 'В этом и смысл, бро...', 'Двигается'
Ты любишь смешивать фразы и придумывать собственные вариации
Ты пишешь короткие и ёмкие сообщения, лаконично умудряясь быть быдлом и философом - похвалить и обосрать спортсмена
"""

def llm_generate_personal_stats(sportsmen: str, podhod_history: str):
    chat_response = client.chat.complete(
        model= model,
        temperature=0.85,
        safe_prompt=False,
        messages = [
            {
                "role": "system",
                "content": f"""
                {core_character}
                Дана история подходов спортсмена {sportsmen} за отчётный период и нужно оценить как спортсмен двигается:
                {podhod_history}
                
                Не пиши длинных сообщений! Ограничься самым важным!
                Не используй форматирование. Только текст
                """,
            },
            {
                "role": "user",
                "content": f'Спорстмен {sportsmen} запросил статистику и оценку по своим подходам',
            },
        ]
    )
    resp = chat_response.choices[0].message.content
    if resp == '':
        return ' '
    return resp

def llm_generate_general_stats(podhod_history: str):
    chat_response = client.chat.complete(
        model= model,
        temperature=0.85,
        safe_prompt=False,
        messages = [
            {
                "role": "system",
                "content": f"""
                {core_character}
                Дана история подходов всех спортсменов за отчётный период и нужно оценить как они в целом двигаются:
                {podhod_history}
                
                Тут нужен детальный анализ и выявление скрытых связей
                Не используй форматирование. Только текст
                """,
            },
            {
                "role": "user",
                "content": f'Организаторы запросили отчёт по алкогольным движениям',
            },
        ]
    )
    resp = chat_response.choices[0].message.content
    if resp == '':
        return ' '
    return resp
