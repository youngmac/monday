import os
import time
import requests
from dotenv import load_dotenv


class USPSApi:
    TOKEN_URL = "https://apis.usps.com/oauth2/v3/token"
    BASE_URL = "https://apis.usps.com"

    # testing
    SANDBOX_BASE_URL = "https://apis-tem.usps.com"
    SANDBOX_TOKEN_URL = "https://apis-tem.usps.com/oauth2/v3/token"

    # TOKEN_URL = SANDBOX_TOKEN_URL
    # BASE_URL = SANDBOX_BASE_URL

    def __init__(self, env_dir):
        load_dotenv(os.path.join(env_dir, ".pick_sheets_env"))

        self.client_id = os.getenv("USPS_CLIENT_ID")
        self.client_secret = os.getenv("USPS_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise Exception("Missing USPS_CLIENT_ID or USPS_CLIENT_SECRET")

        self.access_token = None
        self.token_expiration = 0

        self._authenticate()

    def _authenticate(self):
        """
        Requests an OAuth bearer token and stores it.
        """

        response = requests.post(
            self.TOKEN_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        self.access_token = data["access_token"]

        # Refresh 60 seconds early
        self.token_expiration = time.time() + data["expires_in"] - 60

    def _ensure_authenticated(self):
        """
        Refreshes the token if necessary.
        """

        if time.time() >= self.token_expiration:
            self._authenticate()

    def _headers(self):
        self._ensure_authenticated()

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

    def _get_transit_time(self, origin_zip, destination_zip, mail_class):
        """
        Generic USPS transit time lookup.

        Returns transit time in days.
        """

        endpoint = f"{self.BASE_URL}/service-standards/v3/estimates"

        response = requests.get(
            endpoint,
            headers=self._headers(),
            params={
                "originZIPCode": origin_zip,
                "destinationZIPCode": destination_zip,
                "mailClass": mail_class
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        # Temporary - inspect actual response during testing
        # print(data)

        return int(data[0]["serviceStandard"])
    
    def get_priority_mail_time(self, origin_zip, destination_zip):
        """
        Returns USPS Priority Mail transit time in days.
        """

        return self._get_transit_time(
            origin_zip,
            destination_zip,
            "PRIORITY_MAIL"
        )


    def get_ground_adv_transit_time(self, origin_zip, destination_zip):
        """
        Returns USPS Ground Advantage transit time in days.
        """

        return self._get_transit_time(
            origin_zip,
            destination_zip,
            "USPS_GROUND_ADVANTAGE"
        )



class UPSApi:
    """
    UPS API wrapper.
    """

    TOKEN_URL = "https://onlinetools.ups.com/security/v1/oauth/token"
    BASE_URL = "https://onlinetools.ups.com"

    # testing
    SANDBOX_BASE_URL = "https://wwwcie.ups.com"
    SANDBOX_TOKEN_URL = "https://wwwcie.ups.com/security/v1/oauth/token"

    # TOKEN_URL = SANDBOX_TOKEN_URL
    # BASE_URL = SANDBOX_BASE_URL

    def __init__(self, env_dir="."):
        load_dotenv(os.path.join(env_dir, ".pick_sheets_env"))

        self.client_id = os.getenv("UPS_CLIENT_ID")
        self.client_secret = os.getenv("UPS_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise Exception(
                "Missing UPS_CLIENT_ID or UPS_CLIENT_SECRET"
            )

        self.access_token = None
        self.token_expiration = 0

        self._authenticate()

    def _authenticate(self):
        """
        Requests a UPS OAuth bearer token.
        """

        response = requests.post(
            self.TOKEN_URL,
            auth=(
                self.client_id,
                self.client_secret
            ),
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "client_credentials"
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        self.access_token = data["access_token"]

        # Refresh slightly early
        self.token_expiration = (
            time.time()
            + int(data["expires_in"])
            - 60
        )

    def _ensure_authenticated(self):
        """
        Refresh token if expired.
        """

        if time.time() >= self.token_expiration:
            self._authenticate()

    def _headers(self):
        self._ensure_authenticated()

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "transId": str(int(time.time())),
            "transactionSrc": "pick_sheets"
        }

    def get_ground_transit_time(self, origin_zip, destination_zip, destination_city, destination_state):
        """
        Returns UPS Ground transit time in days.
        """
        # return 0

        endpoint = (
            f"{self.BASE_URL}"
            "/api/shipments/v1/transittimes"
        )

        payload = {
            "originCountryCode": "US",
            "originPostalCode": origin_zip,
            "destinationCountryCode": "US",
            "destinationPostalCode": destination_zip,
            "destinationCityName": destination_city.upper().replace("TOWNSHIP", "").replace(" ", ""),
            "destinationStateProvince": destination_state,
            "weight": "1",
            "weightUnitOfMeasure": "LBS",
            "numberOfPackages": "1"
        }

        response = requests.post(
            endpoint,
            headers=self._headers(),
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        # import json
        # print("UPS RAW RESPONSE:")
        # print(json.dumps(data, indent=4))

        services = data["emsResponse"]["services"]

        for service in services:
            if service["serviceLevel"] == "GND":
                return service["businessTransitDays"]

        raise Exception("UPS Ground service not available")


class ShippingTransitTime:
    """
    Unified wrapper for carrier transit time lookups.
    """

    def __init__(self, env_dir="."):
        self.usps = USPSApi(env_dir)
        self.ups = UPSApi()

        # Cache transit time lookups for this run
        self._cache = {}

    def get_all_transit_times(self, origin_zip, destination_zip, destination_city, destination_state):
        """
        Returns all available transit times in a consistent format.
        """

        # return { # toggle to turn off api usage
        #     "usps_priority_mail": 0,
        #     "usps_ground_advantage": 0,
        #     "ups_ground": 0
        # }

        cache_key = (origin_zip, destination_zip, destination_city, destination_state)

        if cache_key in self._cache:
            return self._cache[cache_key]
        
        priority_time = 99
        ground_adv_time = 99
        ground_time = 99
        i = 0

        while (priority_time == 99 or ground_adv_time == 99 or ground_time == 99) and i < 3:
            if i > 0:
                print(f"Wait 10 seconds and retrying transit time lookup for {origin_zip} to {destination_zip} (Attempt: {i + 1})...")
                time.sleep(10)
            if priority_time == 99:
                try: 
                    priority_time = self.usps.get_priority_mail_time(
                        origin_zip,
                        destination_zip
                    )
                except Exception as e:
                    print(f"Error fetching USPS Priority Mail transit time: {e}")
                    print(e)
            if ground_adv_time == 99:
                try:
                    ground_adv_time = self.usps.get_ground_adv_transit_time(
                        origin_zip,
                        destination_zip
                    )
                except Exception as e:
                    print(f"Error fetching USPS Ground Advantage transit time: {e}")
                    print(e)
            if ground_time == 99:
                try:    
                    ground_time = self.ups.get_ground_transit_time(
                        origin_zip,
                        destination_zip,
                        destination_city,
                        destination_state
                    )
                except Exception as e:
                    print(f"Error fetching UPS Ground transit time: {e}")
                    print(e)

            i += 1
            
        
        transit_times = {
            "usps_priority_mail": priority_time,
            "usps_ground_advantage": ground_adv_time,
            "ups_ground": ground_time
        }
        self._cache[cache_key] = transit_times
        return transit_times