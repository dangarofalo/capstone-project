"""Log collectors. Each one reads new security events since its last checkpoint.

A collector has two methods:
    collect() -> list[dict]   new events, in the shape the API expects
    commit()                  save the checkpoint (call only after the server accepted them)
"""


def get_collector(config: dict):
    source = config.get("source", "windows")
    if source == "windows":
        from .windows import WindowsCollector

        return WindowsCollector(config)
    if source == "linux":
        from .linux import LinuxCollector

        return LinuxCollector(config)
    raise ValueError(f"Unknown source '{source}'. Use 'windows' or 'linux'.")
