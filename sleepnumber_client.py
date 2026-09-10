import requests
import random
import time


class SleepNumberClient:
    API_BASE = "https://prod-api.sleepiq.sleepnumber.com/rest"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": random.choice(self.USER_AGENTS)})
        self._key = None

    def login(self):
        self._key = None
        r = self._session.put(
            f"{self.API_BASE}/login",
            json={"login": self._username, "password": self._password},
            timeout=30,
        )
        if r.status_code == 401:
            raise ValueError("Incorrect username or password")
        if r.status_code == 403:
            self._session.headers.update({"User-Agent": random.choice(self.USER_AGENTS)})
            raise ValueError(f"User-Agent blocked (HTTP 403). Retry with a different agent.")
        r.raise_for_status()
        data = r.json()
        self._key = data["key"]
        return data

    def _request(self, path, method="get", params=None, json_data=None, _retry=0):
        if self._key is None:
            self.login()

        url = f"{self.API_BASE}{path}"
        req_params = {"_k": self._key}
        if params:
            req_params.update(params)

        if method == "put":
            r = self._session.put(url, params=req_params, json=json_data, timeout=30)
        else:
            r = self._session.get(url, params=req_params, timeout=30)

        if r.status_code in (401, 404) and _retry < 2:
            self.login()
            return self._request(path, method, params, json_data, _retry + 1)
        if r.status_code == 403 and _retry < 2:
            self._session.headers.update({"User-Agent": random.choice(self.USER_AGENTS)})
            self.login()
            return self._request(path, method, params, json_data, _retry + 1)

        r.raise_for_status()
        return r.json()

    def get_sleepers(self):
        return self._request("/sleeper")["sleepers"]

    def get_beds(self):
        return self._request("/bed")["beds"]

    def get_family_status(self):
        return self._request("/bed/familyStatus")["beds"]

    def get_sleep_data(self, sleeper_id, date, interval="D1"):
        """Fetch sleep data. interval='D1' for 1 day, 'M1' for 1 month."""
        return self._request("/sleepData", params={
            "date": date,
            "interval": interval,
            "sleeper": sleeper_id,
        })

    def get_sleep_slice_data(self, sleeper_id, date):
        """Fetch time-series sleep state data for a single day."""
        return self._request("/sleepSliceData", params={
            "date": date,
            "sleeper": sleeper_id,
        })

    def get_monthly_slice(self, sleeper_id, date):
        """Fetch monthly summary slice data."""
        return self._request(f"/sleeper/{sleeper_id}/monthlySlice", params={
            "date": date,
        })
