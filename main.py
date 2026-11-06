from src.app import run


def open_when_ready() -> None:
    """Open the local UI once the server is accepting requests."""
    import time
    import urllib.request
    import webbrowser

    url = "http://127.0.0.1:8765"
    for _ in range(100):
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            pass
        time.sleep(0.2)


if __name__ == "__main__":
    import threading

    threading.Thread(target=open_when_ready, daemon=True).start()
    run()
