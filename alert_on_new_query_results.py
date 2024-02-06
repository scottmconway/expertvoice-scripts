#!/usr/bin/env python3

import argparse
import json
import logging
import logging.config
import os

import expertvoice_client

APP_NAME = "expertvoice_alert_on_new_query_results"

# TODO overhaul seen listings method
# instead of being date based, we should instead just pull product IDs
# if it's in seen listings, don't alert on it (but track it)
# at end of execution, write all results (ignoring seen listings) to seen_listings file


def main():
    parser = argparse.ArgumentParser()
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument(
        "-q", "--query-name", type=str, nargs=1, help="The name of the query to execute"
    )
    query_group.add_argument(
        "--all",
        action="store_true",
        help="If set, execute all queries for the configured data source",
    )
    parser.add_argument(
        "-l",
        "--list-queries",
        action="store_true",
        help="If set, list all queries that can be executed "
        "for the current data source and exit",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="If set, log URLs in markdown format (for gotify)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="./config.json",
        help="The path to a configuration file to use. Defaults to ./config.json",
    )

    args = parser.parse_args()

    # load config
    with open(args.config) as f:
        config = json.load(f)

    # logging setup
    logging.config.dictConfig(config.get("logging", {"version": 1}))
    logger = logging.getLogger(APP_NAME)

    if args.list_queries:
        print("Saved queries: %s" % (", ".join(sorted(config["saved_queries"].keys()))))
        return

    # init seen listings
    seen_listings_filename = config.get("seen_listings_filename", "seen_listings.json")
    if os.path.isfile(seen_listings_filename):
        with open(seen_listings_filename, "r") as f:
            seen_listings = json.load(f)
    else:
        seen_listings = dict()

    if args.all:
        queries_to_run = config["saved_queries"]
    else:
        queries_to_run = {args.query_name: config["saved_queries"][args.query_name]}

    ev = expertvoice_client.ExpertvoiceClient(config)
    new_seen_listings = dict()

    for query_name, query_json in queries_to_run.items():
        query_res = ev.search_products(**query_json)

        alert_queue = list()

        for listing in query_res:
            item_id = str(listing["productCode"])
            new_seen_listings[item_id] = ""

            # skip seen listings
            if item_id in seen_listings:
                continue

            listing["url"] = ev.get_product_url(
                listing["orgId"], listing["productCode"]
            )
            alert_queue.append(listing)

        if alert_queue:
            formatted_msg_lines = [
                f'{len(alert_queue)} new results for ExpertVoice query "{query_name}"',
                "",
            ]
            for alert in alert_queue:
                if args.markdown:
                    alert_lines = [
                        f"[{alert['brand']} - {alert['name']}]({alert['url']}):",
                        "",
                        f"price: {alert['price']}, msrp: {alert['msrp']}",
                        "",
                    ]

                else:
                    alert_lines = [
                        f"{alert['brand']} - {alert['name']}:",
                        f"price: {alert['price']}, msrp: {alert['msrp']}",
                        alert["url"],
                        "",
                    ]
                formatted_msg_lines.extend(alert_lines)

            logger.info("\n".join(formatted_msg_lines))

    # save new results of seen listings

    # but before we do, trim the stale entries
    # TODO how to determine stale entries?
    # I guess it'd be "anything we didn't see"
    # doesn't have to be time-based
    keys_to_drop = list()

    # for item_id, end_time in seen_listings.items():
    #    if now > datetime.datetime.fromisoformat(end_time):
    #        keys_to_drop.append(item_id)

    # for item_id in keys_to_drop:
    #    del seen_listings[item_id]

    with open(seen_listings_filename, "w") as f:
        json.dump(new_seen_listings, f)


if __name__ == "__main__":
    main()
