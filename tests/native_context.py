"""Minimal native host context for offline registration fixtures."""

class Context:
    def __init__(self):
        self.skills = {}
        self.commands = {}
        self.cli_commands = []
        self.messages = []
        self.accept = True

    def register_skill(self, name, path):
        self.skills[name] = path

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands[name] = handler

    def register_cli_command(self, name, *args, **kwargs):
        self.cli_commands.append(name)

    def get_config(self, key, default=None):
        # Config persistence is exercised against the real Hermes loader in
        # integration_plugin.py; these contracts isolate command registration.
        if key == 'apply_runtime_defaults':
            return False
        return default

    def inject_message(self, content, **kwargs):
        self.messages.append((content, kwargs))
        return self.accept
