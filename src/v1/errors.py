from aiohttp.web import json_response


missing_currency_error = json_response({"error": "missing currency"}, status=400)
currency_not_found_error = json_response({"error": "currency not found"}, status=400)
json_parse_error = json_response({"error": "parsing json failed"}, status=400)
bad_request_error = json_response({"error": "bad request"}, status=400)

class CurrencyNotFoundError(Exception):
    pass

class CurrencyValueError(ValueError):
    pass

class WalletNotFoundError(Exception):
    pass