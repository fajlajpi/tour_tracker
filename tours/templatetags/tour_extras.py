from django import template

register = template.Library()


@register.filter
def sum_tips_czk(tips):
    return sum(tip.amount_in_czk() for tip in tips)


@register.filter
def div(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return None


@register.filter
def get_item(dictionary, key):
    """Allow dict lookup with a variable key: {{ mydict|get_item:variable }}"""
    return dictionary.get(key, [])