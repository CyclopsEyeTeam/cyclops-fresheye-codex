"""Selected app target and a small host-side availability check; no app startup."""
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .paths import UserError


def validate_app_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        raise UserError('--app requires an http:// or https:// URL')
    if parts.username or parts.password:
        raise UserError('Use browser sign-in rather than credentials embedded in an app URL')
    return url


def probe_app(url):
    result = {'url': url, 'checkedAt': datetime.now(timezone.utc).isoformat()}
    try:
        with urlopen(Request(url, headers={'User-Agent': 'Cyclops-FreshEye-app-check'}), timeout=2) as response:
            result.update(reachable=True, httpStatus=response.status)
    except HTTPError as exc:
        # An HTTP error still proves that a server is already responding.
        result.update(reachable=True, httpStatus=exc.code)
        exc.close()
    except (URLError, OSError) as exc:
        result.update(reachable=False, error=type(exc).__name__)
    return result


def app_context(probe):
    text = '\n\nSelected app test target: '+probe['url']+'\n'
    if probe['reachable']:
        text += ('Host availability check: HTTP '+str(probe['httpStatus'])+'. '
                 'Reuse the running service: open this URL with the browser tools. '
                 'Do not start, stop or restart a server that is already responding. '
                 'If it later becomes unreachable, recheck availability before deciding whether startup is needed.')
    else:
        text += ('The host check did not reach this URL. Check it with the browser tools first. '
                 'Only start a local server if the intended task calls for it and no service is already responding.')
    return text
