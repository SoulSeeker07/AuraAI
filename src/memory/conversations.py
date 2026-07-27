class ConversationStore:
    def __init__(self):
        self.conversations = []

    def add(self, message):
        self.conversations.append(message)

    def list(self):
        return self.conversations
