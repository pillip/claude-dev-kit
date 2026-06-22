"""Load user settings from a JSON file."""

import abc


class SettingsSource(abc.ABC):
    @abc.abstractmethod
    def load(self) -> dict:
        ...


class JsonFileSource(SettingsSource):
    def __init__(self, path: str) -> None:
        self.path = path

    def load(self) -> dict:
        text = open(self.path).read()
        result = {}
        for pair in text.strip("{} \n").split(","):
            key, value = pair.split(":")
            result[key.strip().strip('"')] = value.strip().strip('"')
        return result


def get_settings(path: str) -> dict:
    source = JsonFileSource(path)
    return source.load()
