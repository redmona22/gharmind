import re

_OPT = re.compile(
    r"^\s*(stop|stop all|stop messages?|stop messaging|unsubscribe|opt[\s-]?out|cancel subscription)\s*[.!]*\s*$",
    re.I,
)


def is_opt_out(text: str) -> bool:
    return bool(_OPT.match(text or ""))
