import urllib.parse
from typing import Dict, List, Optional

import requests
from requests.exceptions import JSONDecodeError


def flatten_taxonomy(
    category: Dict,
    parent_name: Optional[str] = None,
    short_category_name: Optional[bool] = False,
) -> List[Dict]:
    result = list()
    if not short_category_name and parent_name:
        category["name"] = f"{parent_name} -> {category['name']}"
    result.append(category)

    # Check if the current category has nested taxonomy
    if "taxonomy" in category:
        # Recursively flatten the nested taxonomy and extend the result list
        for sub_category in category["taxonomy"]:
            result.extend(
                flatten_taxonomy(
                    sub_category,
                    parent_name=category["name"],
                    short_category_name=short_category_name,
                )
            )

    return result


class ExpertvoiceClient:
    LOGIN_LANDING_PAGE = "https://www.expertvoice.com/sign-in"
    LOGIN_URL = "https://www.expertvoice.com/sign-on/service/sign-in"
    API_ROOT = "https://www.expertvoice.com/xapi"
    CATEGORY_URL = f"{API_ROOT}/store-services/ext/v1/stores/taxonomy/browse"

    GENDERS = {"Men's", "Women's", "Youth", "Unisex"}
    PROMOTION_LOOKUP = {
        "extra_savings": 5,
        "free_shipping": 6,
        "outlet": 7,
        "flash_deal": 8,
        "friends_and_family": 9,
    }

    def __init__(self, config: Dict):
        self.expertvoice_session = requests.Session()
        self.expertvoice_session.hooks[
            "response"
        ] = lambda r, *args, **kwargs: err_hook(r)
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

    def get_product_url(self, org_id, product_code) -> str:
        return (
            f"https://www.expertvoice.com/product/bottom_text/{org_id}?p="
            + urllib.parse.quote(product_code)
        )

    def get_categories(
        self, depth: Optional[int] = None, short_category_name: Optional[bool] = False
    ) -> List[Dict]:
        res = self.expertvoice_session.get(
            ExpertvoiceClient.CATEGORY_URL, params={"depth": depth}
        ).json()

        categories = list()
        for category_group in res["browse"]:
            categories.extend(
                flatten_taxonomy(
                    category_group, short_category_name=short_category_name
                )
            )

        return categories

    def search_products(
        self,
        search_term: str = "",
        genders: Optional[List[str]] = None,
        brands: Optional[List[int]] = None,
        category_id: Optional[int] = None,
        promotion_extra_savings: bool = False,
        promotion_free_shipping: bool = False,
        promotion_friends_and_family: bool = False,
        promotion_outlet: bool = False,
        promotion_flash_deal: bool = False,
        hide_out_of_stock: bool = False,
    ) -> List[Dict]:
        # TODO expand search option filters

        configuration_override_filters = {"TRAIT_PER_DEAL": []}

        # set filters
        if hide_out_of_stock:
            configuration_override_filters["IN_STOCK_DEAL"] = ["true"]
        if category_id:
            configuration_override_filters["TAXONOMY"] = [category_id]
        if genders:
            # TODO check all values againt ExpertvoiceClient.GENDERS
            # TODO do these need to be ordered in any specific way?
            configuration_override_filters["TRAIT.3"] = genders

        if brands:
            configuration_override_filters["ORGANIZATION"] = brands

        # TODO source PROMOTION_LOOKUP
        if promotion_extra_savings:
            configuration_override_filters["TRAIT_PER_DEAL"].append(5)

        if promotion_free_shipping:
            configuration_override_filters["TRAIT_PER_DEAL"].append(6)

        if promotion_outlet:
            configuration_override_filters["TRAIT_PER_DEAL"].append(7)

        if promotion_flash_deal:
            configuration_override_filters["TRAIT_PER_DEAL"].append(8)

        if promotion_friends_and_family:
            configuration_override_filters["TRAIT_PER_DEAL"].append(9)

        # gotta love seeing lists of JSON objects
        products_json = {
            "providerConfigurations": [
                {
                    "configurationOverrides": {
                        "filters": {"accessLevels": ["full", "limited", "none"]},
                        "maxResults": 250,
                        "startResults": None,
                    },
                    "key": "entity-search",
                },
                {
                    "configurationOverrides": {
                        "filters": {},
                        "maxResults": 100,
                        "providerTimeoutMS": 10000,
                        "startResults": 0,
                    },
                    "key": "user",
                },
                {
                    "configurationOverrides": {"filters": {}, "maxResults": 5000},
                    "key": "module",
                },
                {
                    "configurationOverrides": {
                        "filters": configuration_override_filters,
                        "maxResults": 36,
                        "startResults": 0,
                        "options": {"ZCFCTS": True},
                        "providerTimeoutMS": 5000,
                    },
                    "key": "ProductSearchProvider",
                },
            ],
            "requestedProviders": ["ProductSearchProvider"],
            "searchConfiguration": {
                "providerTimeoutMS": 1500,
                "startResults": 0,
                "sortDirection": "DESC",
                "sortField": "id",
            },
            "searchTerm": search_term,
        }
        results = list()
        total_results = -1  # for kick-off
        while len(results) < total_results or total_results == -1:
            page_res = self.expertvoice_session.post(
                f"{ExpertvoiceClient.API_ROOT}/search/ext/2.0/search",
                json=products_json,
                # ).json()['providerResults']['ProductSearchProvider']
            ).json()["providerResults"]["ProductSearchProvider"]
            total_results = page_res[
                "totalResults"
            ]  # TODO I don't want to keep setting this...

            # TODO the last page likes to over-fill the buffer, and repeat
            for item in page_res["resultItems"]:
                results.append(
                    {
                        "brand": item["owner"]["name"],
                        "name": item["text"],
                        "price": item["metadata"]["price"],
                        "msrp": item["metadata"]["retailPrice"],
                        "orgId": item["metadata"]["orgId"],
                        "productCode": item["metadata"]["productCode"],
                    }
                )

            # TODO we know the index since we wrote it,
            # but we should find this configuration by
            # searching for the dict with `key == "ProductSearchProvider"`
            products_json["providerConfigurations"][3]["configurationOverrides"][
                "startResults"
            ] += len(page_res["resultItems"])

        return results

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
        total_results = -1  # for kick-off
        while len(results) < total_results or total_results == -1:
            page_res = self.expertvoice_session.post(
                "https://www.expertvoice.com/xapi/store-services/ext/v1/stores/search/products",
                json=products_json,
            ).json()
            total_results = page_res[
                "totalResults"
            ]  # TODO I don't want to keep setting this...
            for item in page_res["resultItems"]:
                results.append(
                    {
                        "brand": item["owner"]["name"],
                        "name": item["text"],
                        "price": item["metadata"]["price"],
                        "msrp": item["metadata"]["retailPrice"],
                    }
                )

            products_json["searchConfiguration"]["startResults"] += len(
                page_res["resultItems"]
            )

        return results


def err_hook(res):
    res.raise_for_status()

    try:
        js = res.json()
    except JSONDecodeError:
        return

    if js.get("err", None):
        raise BaseException(f"API Exception - {js.get('errorMessage', '')}")
