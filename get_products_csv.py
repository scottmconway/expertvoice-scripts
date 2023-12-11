#!/usr/bin/env python3

import argparse
import csv
import json

from expertvoice_client import ExpertvoiceClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        default="./config.json",
        help="The path to a configuration file to use. Defaults to ./config.json",
    )
    parser.add_argument(
        "-o",
        "--out-path",
        type=str,
        default="./out.csv",
        help="The path at which to save the products CSV. Defaults to ./out.csv",
    )
    parser.add_argument(
        "--short-category-names",
        action="store_true",
        help="If set, only show the bottom-most level in category names"
    )
    parser.add_argument(
        "--category-ids",
        type=int,
        nargs="*",
        help="If specified, any number of category IDs. "
        "Else, all categories will be downloaded",
    )
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)

    ev = ExpertvoiceClient(config)
    all_products = dict()

    categories = ev.get_categories(depth=6, short_category_name=args.short_category_names)
    product_rows = list()

    for category_dict in categories:
        category_products = list()
        if args.category_ids:
            if "id" in category_dict and category_dict["id"] in args.category_ids:
                category_products = ev.get_products(category_id=category_dict["id"])

        elif "taxonomy" not in category_dict:
            all_products[category_dict["name"]] = ev.get_products(category_dict["id"])
            category_products = ev.get_products(category_dict["id"])

        for product in category_products:
            product.pop("orgId", None)
            product.pop("productCode", None)
            product_rows.append({**product, **{"category": category_dict["name"]}})

    with open(args.out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=product_rows[0].keys())
        writer.writeheader()
        writer.writerows(product_rows)


if __name__ == "__main__":
    main()
