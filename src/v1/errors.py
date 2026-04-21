from aiohttp.web import json_response


missing_currency_error = json_response({"error": "missing currency"}, status=400)