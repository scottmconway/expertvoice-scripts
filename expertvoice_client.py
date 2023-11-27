#!/usr/bin/env python3

from typing import Dict, List

import requests
from requests.exceptions import JSONDecodeError

class ExpertvoiceClient:
    LOGIN_LANDING_PAGE = "https://www.expertvoice.com/sign-in"
    LOGIN_URL = "https://www.expertvoice.com/sign-on/service/sign-in"
    CATEGORY_URL = (
        "https://www.expertvoice.com/xapi/store-services/ext/v1/stores/taxonomy/browse"
    )

    def __init__(self, config: Dict):
        self.expertvoice_session = requests.Session()
        self.expertvoice_session.hooks["response"] = lambda r, *args, **kwargs: err_hook(r)
        self.expertvoice_session.headers[
            "User-Agent"
        ] = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0"

        self.expertvoice_session.get(
            ExpertvoiceClient.LOGIN_LANDING_PAGE
        )  # set some cookies

        self.expertvoice_session.post(
            ExpertvoiceClient.LOGIN_URL,
            data={
                "identifier": config["auth_info"]["username"],
                "password": config["auth_info"]["password"],
            },
        ).json()

        self.categories = self.get_categories()

    def get_categories(self) -> Dict:
        category_mapping = dict()
        res = self.expertvoice_session.get(ExpertvoiceClient.CATEGORY_URL).json()

        # TODO we might want to rip out the "url" attr so our category URLs don't look suspicious
        for category_group in res["browse"]:
            for category_obj in category_group.get("taxonomy", list()):
                category_mapping[category_obj["id"]] = category_obj["name"]

        return category_mapping

    def get_products(self, category_id: int) -> List[Dict]:
        products_json = {
            "searchTerm": None,
            "searchConfiguration": {
                "filters": {"TAXONOMY": [category_id]},
                "maxResults": 36,
                "options": {
                    "ALGV": None,
                    "CNTXT": "TAXONOMY",
                    "PRFLTR": None,
                    "ZCFCTS": True,
                },
                "sortDirection": "DESC",
                "sortField": "RECOMMENDED",
                "startResults": 0,
            },
        }

        results = list()
        total_results = -1      # for kick-off
        while len(results) < total_results or total_results == -1:
            page_res = self.expertvoice_session.post("https://www.expertvoice.com/xapi/store-services/ext/v1/stores/search/products", json=products_json).json()
            total_results = page_res['totalResults']    # TODO I don't want to keep setting this...
            for item in page_res['resultItems']:
                results.append({
                    "brand": item['owner']['name'],
                    "name": item['text'],
                    "price": item['metadata']['price'],
                    "msrp": item['metadata']['retailPrice']
                    })

            products_json["searchConfiguration"]["startResults"] += len(page_res['resultItems'])

        return results

def err_hook(res):
    res.raise_for_status()

    try:
        js = res.json()
    except JSONDecodeError:
        return

    if js.get("err", None):
        raise BaseException(f"API Exception - {js.get('errorMessage', '')}")
