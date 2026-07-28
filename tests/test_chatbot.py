import json

from Chatbot import ChatBot


def test_chatbot_answers_saved_skills_locally(tmp_path):
    bot = ChatBot(
        db_path=tmp_path / "Memory.db",
        chat_log_path=tmp_path / "ChatLog.json",
    )

    assert bot.ask("I'm learning Palo Alto.") == "Remembered. Skills: Palo Alto"
    assert bot.ask("I'm also studying Juniper.") == "Remembered. Skills: Juniper"

    assert bot.ask("What networking skills do I have?") == (
        "Skills I remember: Juniper, Palo Alto."
    )


def test_chatbot_counts_saved_skills_locally(tmp_path):
    bot = ChatBot(
        db_path=tmp_path / "Memory.db",
        chat_log_path=tmp_path / "ChatLog.json",
    )

    bot.remember("My skills include Python, BGP, GUI")

    assert bot.ask("How many skills do I know?") == (
        "You have 3 skills saved: BGP, GUI, Python."
    )


def test_chatbot_remembers_bare_name_across_instances(tmp_path):
    db_path = tmp_path / "Memory.db"
    chat_log_path = tmp_path / "ChatLog.json"
    bot = ChatBot(db_path=db_path, chat_log_path=chat_log_path)

    assert bot.ask("Sreekanta") == "Got it. Your name is Sreekanta."

    restarted_bot = ChatBot(db_path=db_path, chat_log_path=chat_log_path)
    assert restarted_bot.ask("who am i") == "Your name is Sreekanta."


def test_chatbot_recovers_name_from_existing_chat_log(tmp_path):
    chat_log_path = tmp_path / "ChatLog.json"
    chat_log_path.write_text(
        json.dumps(
            [
                {"role": "user", "content": "who am i"},
                {"role": "assistant", "content": "I do not know your name yet."},
                {"role": "user", "content": "Sreekanta"},
                {"role": "assistant", "content": "Nice to meet you, Sreekanta!"},
            ]
        ),
        encoding="utf-8",
    )

    bot = ChatBot(db_path=tmp_path / "Memory.db", chat_log_path=chat_log_path)

    assert bot.ask("who am i") == "Your name is Sreekanta."
