from num2words import num2words


def money_in_words_ar(amount, currency_name="ريال سعودي", fraction_name="هللة"):
    """Return Arabic amount in words for a given number.

    Usage in Jinja:
        {{ money_in_words_ar(doc.rounded_total or doc.grand_total) }}
    """
    try:
        amount = float(amount or 0)
    except (ValueError, TypeError):
        return ""

    if amount < 0:
        return ""

    main = int(amount)
    fraction = round((amount - main) * 100)

    try:
        main_words = num2words(main, lang="ar")
    except Exception:
        return ""

    if fraction:
        try:
            fraction_words = num2words(fraction, lang="ar")
        except Exception:
            fraction_words = ""
        if fraction_words:
            return f"{main_words} {currency_name} و {fraction_words} {fraction_name} فقط لا غير"

    return f"{main_words} {currency_name} فقط لا غير"
