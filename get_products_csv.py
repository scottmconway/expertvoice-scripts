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
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = json.load(f)

    ev = ExpertvoiceClient(config)
    all_products = dict()

    for category_id, category_name in ev.categories.items():
        all_products[category_name] = ev.get_products(category_id)

    product_rows = list()

    for category_name, products in all_products.items():
        for product in products:
            product["category"] = category_name
            product_rows.append(product)

    with open(args.out_path, "w") as f:
        writer = csv.DictWriter(f, fieldnames=product_rows[0].keys())
        writer.writeheader()
        writer.writerows(product_rows)


if __name__ == "__main__":
    main()
