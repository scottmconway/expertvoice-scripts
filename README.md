# ExpertVoice Scripts
A collection of scripts for programmatically interacting with [ExpertVoice](https://www.expertvoice.com/).

## Requirements
* python3
* see requirements.txt

## Configuration Setup
See `config.json.example` for an example configuration file.

## Scripts
### `get_products_csv.py`

Generates a CSV file of the entire ExpertVoice inventory. CSV entries contain the following values:
* brand
* name
* price
* MSRP (according to ExpertVoice)
* category (Apparel, Accessories, etc.)

Note - as of writing (2023-11-27), ExpertVoice will return an HTTP 500 if you attempt to request product information past the 10,000th element in a given category. The solution to this (while it remains broken on EV's side) is to use nested categories when a given category exceeds 10,000 products. The `depth` parameter in this script is currently hard-coded to `6` to reveal all subcategories. Any value higher than `6` will cause EV to respond with an HTTP 500. Classic.

TODO

#### Arguments
|Short Name|Long Name|Type|Description|
|-|-|-|-|
|`-o`|`--out-path`|`str`|The path at which to save the products CSV. Defaults to ./out.csv|
|N/A|`--config`|`str`|Path to config file - defaults to ./config.json|

### `deal_unlocker.py`

Discovers and unlocks all locked discounts that require passing a learning module campaign in ExpertVoice.
Your account's unlockable deals can be found [here](https://www.expertvoice.com/home/new-to-you).

If run without the `--cheat-sheet` argument, the script will use brute force to enumerate possible answers to questions.
If a cheat sheet is provided, correct answers will be attempted first, before falling back to brute force if the provided answer was incorrect/invalid.

The `--save-cheat-sheet` argument will save the _entire_ cheat sheet - what was discovered during execution as well as the cheat sheet provided by the `--cheat-sheet` argument, if applicable - to a local JSON file.

The paths to `--cheat-sheet` and `--save-cheat-sheet` cannot be the same, as to view the cheat sheet in a read-only context.

My mostly complete cheat sheet can be found [in this repo](https://github.com/scottmconway/expertvoice-scripts/blob/main/cheat_sheet.json), but it may not be perfect! Please feel free to make PRs to update it.

#### Arguments
|Short Name|Long Name|Type|Description|
|-|-|-|-|
|N/A|`--cheat-sheet`|`str`|If provided, the path to a local "cheat sheet" JSON to use for answer lookup|
|N/A|`--save-cheat-sheet`|`str`|If set, save the computed cheat sheet to the provided path after successfully passing quizzes|
|N/A|`--config`|`str`|Path to config file - defaults to ./config.json|

