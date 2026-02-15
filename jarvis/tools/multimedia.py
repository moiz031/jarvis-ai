# jarvis/tools/multimedia.py

import webbrowser

try:
    import pywhatkit
except Exception:
    pywhatkit = None


def open_google():
    """Opens Google search."""
    webbrowser.open("https://www.google.com")
    return "Google open kar diya hai sir."


def play_on_youtube(query: str):
    """Plays a video on YouTube."""
    if pywhatkit is None:
        webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
        return (
            "pywhatkit available nahi tha, isliye YouTube search page open kiya gaya hai."
        )

    pywhatkit.playonyt(query)
    return f"YouTube par '{query}' chala raha hoon sir."


def open_website(url: str):
    """Opens any website."""
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Website {url} open kar di gayi hai."
