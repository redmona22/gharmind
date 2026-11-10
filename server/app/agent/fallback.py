"""Fixed messages used when a human must take over, or the AI cannot be trusted to answer.
Odia and Hindi wording should be reviewed by a native speaker before launch."""

HOLD = {
    "en": "Thanks! One of our team members will contact you shortly.",
    "hi": "धन्यवाद! हमारी टीम का एक सदस्य जल्द ही आपसे संपर्क करेगा।",
    "or": "ଧନ୍ୟବାଦ! ଆମ ଟିମ୍‌ର ଜଣେ ସଦସ୍ୟ ଶୀଘ୍ର ଆପଣଙ୍କ ସହ ଯୋଗାଯୋଗ କରିବେ।",
}

OPT_OUT_CONFIRM = {
    "en": "You have been unsubscribed and will not receive further messages from us.",
    "hi": "आपको अनसब्सक्राइब कर दिया गया है। अब आपको हमारी ओर से कोई संदेश नहीं भेजा जाएगा।",
    "or": "ଆପଣଙ୍କୁ ଅନସବସ୍କ୍ରାଇବ୍ କରାଯାଇଛି। ଆମ ତରଫରୁ ଆଉ କୌଣସି ବାର୍ତ୍ତା ପଠାଯିବ ନାହିଁ।",
}


def hold_message(lang: str | None) -> str:
    return HOLD.get(lang or "en", HOLD["en"])


def opt_out_message(lang: str | None) -> str:
    return OPT_OUT_CONFIRM.get(lang or "en", OPT_OUT_CONFIRM["en"])
