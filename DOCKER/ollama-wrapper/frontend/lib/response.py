from requests import Response

def ErrorResponse(url, err) -> Response:
    response = Response()
    response.status_code = 500
    response.url = url
    response._content = f"ERROR: url={url}, error={err}".encode()
    response.reason = str(err)

    return response
