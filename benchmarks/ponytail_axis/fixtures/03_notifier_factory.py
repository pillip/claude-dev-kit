"""Send a notification to a user."""


class NotifierFactory:
    def create(self, kind: str):
        if kind == "email":
            return EmailNotifier()
        raise ValueError(f"unknown notifier: {kind}")


class EmailNotifier:
    def send(self, to: str, body: str) -> None:
        print(f"emailing {to}: {body}")


def notify_user(email: str, message: str) -> None:
    factory = NotifierFactory()
    notifier = factory.create("email")
    notifier.send(email, message)
