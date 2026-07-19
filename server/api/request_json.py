import json
from typing import Any

from flask import request


class JsonRequestError(ValueError):
    pass


def parse_json_body() -> Any:
    try:
        return json.loads(request.data or b'{}')
    except (TypeError, json.JSONDecodeError) as exc:
        raise JsonRequestError('Malformed JSON request body') from exc