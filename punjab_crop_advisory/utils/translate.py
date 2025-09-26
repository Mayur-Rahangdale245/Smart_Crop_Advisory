from googletrans import Translator

translator = Translator()

def translate_text(text, src="en", dest="pa"):
    try:
        return translator.translate(text, src=src, dest=dest).text
    except:
        return text


