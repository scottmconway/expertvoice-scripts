#!/usr/bin/env python3

import argparse
import datetime
import json
import os
import random
import re
import time
from collections import defaultdict
from typing import Dict, Optional

from requests.exceptions import HTTPError

from expertvoice_client import ExpertvoiceClient

TRAINING_SESSION_REGEX = re.compile(
    r"trainingSessionId(?:['\"]?):\ *[\"']([0-9]+)[\"']"
)


def get_active_campaigns(ev):
    campaign_ids = list()
    res = ev.expertvoice_session.post(
        "https://www.expertvoice.com/xapi/user-content/ext/1.0/content/page/feed/structure/complete/bucket/new-to-you",
        json={},
    ).json()
    for bucket in res["buckets"]:
        if bucket["type"] == "CAMPAIGN":
            campaign_ids = [item["id"] for item in bucket["content"]["items"]]

    return campaign_ids


def take_quiz_for_campaign(
    ev, campaign_id: str, question_answer_cache: Optional[Dict] = None
):
    if question_answer_cache is None:
        question_answer_cache = defaultdict(lambda: {"incorrect": []})

    # goto campaign page, like a user would
    learn_page = ev.expertvoice_session.get(
        "https://www.expertvoice.com/learn/next", params={"campaignId": campaign_id}
    )
    try:
        training_session_id = TRAINING_SESSION_REGEX.findall(learn_page.text)[0]
    except IndexError:
        print("Error - cannot find Training Session ID!")
        return dict(), question_answer_cache

    quiz_form = {"trainingSessionId": training_session_id, "returnType": "json"}

    try:
        quiz_info = ev.expertvoice_session.post(
            "https://www.expertvoice.com/learn/edugame/begin", data=quiz_form
        ).json()
    except HTTPError as he:
        if (
            he.response is not None and he.response.status_code == 415
        ):  # assume this campaign module doesn't have an edugame
            non_quiz_res = ev.expertvoice_session.post(
                "https://www.expertvoice.com/learn/finish",
                params={"trainingSessionId": training_session_id},
                json={},
            ).json()

            if non_quiz_res["nextModuleUrl"]:
                return {
                    "totalModules": 1,
                    "totalModulesPassed": 0,
                }, question_answer_cache
            else:
                return {
                    "totalModules": 1,
                    "totalModulesPassed": 1,
                }, question_answer_cache
        else:
            raise he

    if quiz_info["limitTries"]:
        print(
            f"Error - not attempting quiz for campaign {campaign_id} - "
            f"attempts are limited to {quiz_info['triesRemaining']}"
        )
        return dict(), question_answer_cache

    # TODO there might be timed quizzes
    update_form = {
        "edugameId": quiz_info["id"],
        "timed": "false",
    }

    for question in quiz_info["questions"]:
        # click the "next" button, like a user would
        ev.expertvoice_session.post(
            "https://www.expertvoice.com/learn/edugame/update", data=update_form
        )

        now_mil = round(datetime.datetime.now().timestamp() * 1000)
        start_time = now_mil - random.randint(5000, 10000)

        question_form = {
            "beginTime": str(start_time),
            "endTime": str(now_mil),
            "edugameSessionId": quiz_info["id"],
            "questionId": question["id"],
            "trainingSessionId": training_session_id,
            "questionTime": str(now_mil - start_time),
            "returnType": "json",
        }

        # see if we know the answer (we shouldn't just yet)
        # since we don't know it, guess
        #
        # if we guess right, store the question-answer mapping
        # if we guess wrong, store the _incorrect_ question-answer mapping
        #
        # then nuke our edugame session and try again,
        # this time with more knowledge

        if "incorrect" not in question_answer_cache[question["text"]]:
            question_answer_cache[question["text"]]["incorrect"] = list()

        question_answer_info = question_answer_cache[question["text"]]
        answer_text = None

        # submit the correct answer if we know it
        correct_answer_text = question_answer_info.get("correct", None)
        if correct_answer_text:
            # find the corresponding answer ID
            for answer in question["answers"]:
                if answer["value"] == correct_answer_text:
                    answer_text = answer["value"]
                    question_form["answerId"] = answer["id"]

        # fallback to brute-force if we haven't selected an answerId yet
        if not question_form.get("answerId"):
            for answer in question["answers"]:
                if (
                    answer["value"]
                    in question_answer_cache[question["text"]]["incorrect"]
                ):
                    continue

                else:
                    answer_text = answer["value"]
                    question_form["answerId"] = answer["id"]
                    break

        # They really don't seem to care about bots
        # time.sleep(random.randint(1, 5))

        question_res = ev.expertvoice_session.post(
            "https://www.expertvoice.com/learn/edugame/recordAnswer", data=question_form
        ).json()

        if question_res["correct"]:
            question_answer_cache[question["text"]]["correct"] = answer_text
            question_answer_cache[question["text"]].pop("incorrect", None)

        else:
            # remove this answer from the correct store, if present
            question_answer_cache[question["text"]].pop("correct", None)

            # store the result as incorrect
            question_answer_cache[question["text"]]["incorrect"].append(answer_text)
            # now give up, and return the updated cache
            return dict(), question_answer_cache

    # finish the quiz
    end_form = {
        "edugameSessionId": quiz_info["id"],
        "trainingSessionId": training_session_id,
        "timed": "false",
        "returnType": "json",
    }
    quiz_finish_res = ev.expertvoice_session.post(
        "https://www.expertvoice.com/learn/edugame/end", data=end_form
    )

    print("Quiz completed")
    return quiz_finish_res.json(), question_answer_cache


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cheat-sheet",
        type=str,
        help='If provided, the path to a local "cheat sheet" JSON to use for answer lookup',
    )
    parser.add_argument(
        "--save-cheat-sheet",
        type=str,
        help="If set, save the computed cheat sheet to the provided path after successfully passing quizzes",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="./config.json",
        help="The path to a configuration file to use. Defaults to ./config.json",
    )
    args = parser.parse_args()

    if (
        args.cheat_sheet is not None
        and args.save_cheat_sheet is not None
        and os.path.exists(args.save_cheat_sheet)
        and os.path.samefile(args.cheat_sheet, args.save_cheat_sheet)
    ):
        print(
            "Error - --cheat-sheet and --save-cheat-sheet paths cannot be the same - exiting"
        )
        exit(1)

    with open(args.config, "r") as f:
        config = json.load(f)

    cheat_sheet_map = dict()
    if args.cheat_sheet:
        try:
            with open(args.cheat_sheet, "r") as f:
                cheat_sheet_map = json.load(f)
        except BaseException:
            print(
                f'Error reading cheat sheet "{args.cheat_sheet}" - continuing without it'
            )

    ev = ExpertvoiceClient(config)
    campaign_ids = get_active_campaigns(ev)

    for campaign_id in campaign_ids:
        campaign_solved = False
        campaign_id = str(campaign_id)
        question_answer_cache = defaultdict(
            lambda: {"incorrect": []}, cheat_sheet_map.get(campaign_id, dict())
        )
        try:
            while not campaign_solved:
                print(f"starting campaign {campaign_id}")
                quiz_end_msg, question_answer_cache = take_quiz_for_campaign(
                    ev, campaign_id, question_answer_cache
                )

                # apparently sometimes `isCertified` can be inaccurrate
                # campaign_solved = quiz_end_msg.get('isCertified', False)
                campaign_solved = quiz_end_msg.get(
                    "totalModulesPassed", 0
                ) >= quiz_end_msg.get("totalModules", 1)

        except BaseException:
            print(f"Error in campaign {campaign_id}, continuing")

        # update global correct answers cache
        # strip incorrect answers first, for file size
        if args.save_cheat_sheet and question_answer_cache:
            # strip incorrect answers from Q/A dict before writing to local file
            stripped_qa_dict = dict()
            for question, question_answers in question_answer_cache.items():
                if "correct" in question_answers:
                    stripped_qa_dict[question] = {
                        "correct": question_answers["correct"]
                    }

            if stripped_qa_dict:
                cheat_sheet_map[campaign_id] = stripped_qa_dict
                with open(args.save_cheat_sheet, "w") as f:
                    json.dump(cheat_sheet_map, f, indent=4)


if __name__ == "__main__":
    main()
