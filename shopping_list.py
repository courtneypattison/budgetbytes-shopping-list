#!/usr/bin/env python

from __future__ import print_function

import argparse
from fractions import Fraction
import sys

from measurement.measures import Volume
import bs4
import requests

# todo merge same items, convert units if mergable
# convert fractions to mixed fractions

# things we are very unlikely to need to purchase
EXCLUDE_INGREDIENTS = set([
    'salt',
    'salt and pepper',
    'salt & pepper',
    'freshly cracked black pepper',
    'freshly cracked pepper',
    'water',
    'hot water',
    'pinch of salt',
    'pinch of salt and pepper',
    'freshly ground pepper',
])

UNIMPORTANT_WORDS = [
    '(optional)',
    ', minced',
    ', sliced',
    ', chopped',
    '(any shape)',
    ', divided',
    '*',
    '.',
    ', uncooked',
    'sliced',
    'to taste',
    ', optional',
]

def format_unit(unit):
    unit = unit.rstrip('s').lower()
    aliases = {
        'us_g': ['gallon'],
        'us_qt': ['quart'],
        'us_pint': ['pint'],
        'us_cup': ['cup'],
        'us_oz': ['oz', 'ounce'],
        'us_tbsp': ['tbsp', 'tablespoon'],
        'us_tsp': ['teaspoon', 'tsp'],
        'l': ['l', 'liter', 'litre'],
    }
    translation = { v: k for k, vs in aliases.items() for v in vs}
    if unit in translation:
        return translation[unit]
    return unit


def parse_ingredient(ingredient, adjustment):
    fields = dict()
    for field in ('name', 'amount', 'unit'):
        a = ingredient.findChild('span', attrs={
            'class': 'wprm-recipe-ingredient-%s' % field})
        fields[field] = a.text if a else ''

    # accept fractions and skip 'pinch' of salt etc.
    if fields['amount'].replace('/', '').strip().isdigit():
        amount_per_serving = Fraction(fields['amount']) 
        fields['amount'] = amount_per_serving * adjustment
    else: # assume it is some informal unit (pinch etc.)
        informal_unit = fields['amount'].strip()
        formal_unit = fields['unit'].strip()
        if formal_unit and informal_unit:
            fields['unit'] = informal_unit + ':' + formal_unit 
        else:
            fields['unit'] = informal_unit or formal_unit
        fields['amount'] = adjustment

    fields['unit'] = fields['unit'].replace('.', '').strip().lower()
    name = fields['name'].lower()
    for word in UNIMPORTANT_WORDS:
        name = name.replace(word, '')
    fields['name'] = name.strip()
    return fields

def parse_recipe(site, desired_servings):
    site_code = bs4.BeautifulSoup(site.text, 'html.parser')
    serving_field = site_code.find('span', attrs={'class': 'wprm-recipe-servings'})
    if serving_field:
        servings = int(serving_field.text)
    else:
        servings = desired_servings
    output = {'title': site_code.find('h1', attrs={
        'class': 'title'}).text}
    ingredient_list = []
    output['ingredients'] = ingredient_list
    for ingredient in site_code.find_all(
            'li', attrs={'class': 'wprm-recipe-ingredient'}):
        fields = parse_ingredient(ingredient, Fraction(desired_servings, servings))
        if fields['name'] not in EXCLUDE_INGREDIENTS:
            ingredient_list.append(fields)
    return output

def format_ingredients(ingredients):
    return ('\n'.join(' - {amount} [{unit}] {name}'.format(**ingredient)
        for ingredient in ingredients))

def format_recipes(recipes):
    return ('\n'.join(r['title'] + '\n' +
        format_ingredients(r['ingredients']) for r in recipes))

def get_recipes(recipes, servings):
    output = []
    for recipe in recipes:
        site = requests.get(recipe)
        if site.status_code == requests.codes.ok:
            output.append(parse_recipe(site, servings))
        else:
            print('failed to fetch:{} response code:{}'.format(
                recipe, site.status_code), file=sys.stderr)
    return output

def to_shopping_list(recipes):
    total = dict()
    for recipe in recipes:
        for ingredient in recipe['ingredients']:
            name = ingredient['name']
            unit = ingredient['unit']
            amount = ingredient['amount']
            if (name, unit) in total:
                total[name, unit]['amount'] += amount
            else:
                total[name, unit] = {
                    'name': name,
                    'unit': unit,
                    'amount': amount,
                }
    return sorted(total.values(), key=lambda k: k['name'])

def format_shopping_list(shopping_list):
    return 'Shopping List\n' + format_ingredients(shopping_list)

def read_choices(fromfile):
    choices = []
    if fromfile:
        for line in fromfile:
            if line.strip().startswith('+'):
                name, _ = line.strip(' +\t').split(' ')
                choices.append(name)
    return choices


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', nargs='*')
    parser.add_argument('--servings', type=int, default=6)
    parser.add_argument('--fromfile', type=argparse.FileType('r'))
    args = parser.parse_args()
    urls = ['https://www.budgetbytes.com/' + url for url in (args.url + read_choices(args.fromfile))]
    text = format_shopping_list(to_shopping_list(get_recipes(urls, args.servings)))
    print(text)

if __name__ == "__main__":
    main()
