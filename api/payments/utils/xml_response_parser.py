from __future__ import annotations

from typing import TypeAlias
from xml.etree import ElementTree

from api.exceptions import PaymentInvalidProviderResponseError


JsonValue: TypeAlias = str | dict[str, "JsonValue"] | list["JsonValue"]

XML_RESPONSE_PREVIEW_LENGTH = 1000
XML_ATTRIBUTES_KEY = "attributes"
XML_TEXT_ROOT = "text"
XML_TEXT_VALUE_KEY = "value"


def parse_paygine_response(raw_response: str) -> dict[str, object]:
    """Преобразуем ответ Paygine в читаемый dict."""
    response = raw_response.strip().lstrip("\ufeff")

    if not response.startswith("<"):
        return {
            "root_tag": XML_TEXT_ROOT,
            "data": {XML_TEXT_VALUE_KEY: response},
        }

    try:
        root = ElementTree.fromstring(response)
    except ElementTree.ParseError as exc:
        raise PaymentInvalidProviderResponseError(
            details={"raw_response": response[:XML_RESPONSE_PREVIEW_LENGTH]}
        ) from exc

    return {
        "root_tag": _tag_name(root.tag),
        "data": _node_to_value(root),
    }


def xml_leaf_values(data: object, excluded_keys: set[str] | None = None) -> list[str]:
    """Возвращаем значения листовых XML-тегов в порядке обхода."""
    excluded_keys = excluded_keys or set()

    if isinstance(data, str):
        return [data]

    if isinstance(data, list):
        return [
            value
            for item in data
            for value in xml_leaf_values(item, excluded_keys)
        ]

    if not isinstance(data, dict):
        return []

    return [
        value
        for key, item in data.items()
        if key != XML_ATTRIBUTES_KEY and key not in excluded_keys
        for value in xml_leaf_values(item, excluded_keys)
    ]


def _children_to_dict(node: ElementTree.Element) -> dict[str, JsonValue]:
    """Преобразуем дочерние XML-теги в dict."""
    result: dict[str, JsonValue] = {}

    if node.attrib:
        result[XML_ATTRIBUTES_KEY] = dict(node.attrib)

    for child in node:
        _append_value(result, _tag_name(child.tag), _node_to_value(child))

    return result


def _node_to_value(node: ElementTree.Element) -> JsonValue:
    """Преобразуем XML-узел в JSON-совместимое значение."""
    if list(node):
        return _children_to_dict(node)

    value = (node.text or "").strip()
    if not node.attrib:
        return value

    return {
        XML_ATTRIBUTES_KEY: dict(node.attrib),
        XML_TEXT_VALUE_KEY: value,
    }


def _append_value(data: dict[str, JsonValue], key: str, value: JsonValue) -> None:
    """Добавляем значение XML-тега с учетом повторяющихся тегов."""
    if key not in data:
        data[key] = value
        return

    current_value = data[key]
    if isinstance(current_value, list):
        current_value.append(value)
    else:
        data[key] = [current_value, value]


def _tag_name(tag: str) -> str:
    """Возвращаем имя XML-тега без namespace."""
    return tag.rsplit("}", 1)[-1].lower()
