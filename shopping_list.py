#!/usr/bin/env python

from __future__ import print_function

import argparse
from fractions import Fraction
import sys

import requests
import bs4

def parse_ingredient(ingredient, adjustment):
    fields = dict()
    for field in ('name', 'amount', 'unit'):
        a = ingredient.findChild('span', attrs={
            'class': 'wprm-recipe-ingredient-%s' % field})
        fields[field] = a.text if a is not None else ''

    # accept fractions and skip 'pinch' of salt etc.
    if fields['amount'].replace('/', '').isdigit():
        amount_per_serving = Fraction(fields['amount']) 
        fields['amount'] = amount_per_serving * adjustment
    else: # assume it is some informal unit (pinch etc.)
        fields['unit'] = fields['amount'] + ':' + fields['unit']
        fields['amount'] = adjustment

    fields['name'] = fields['name'].lower()
    return fields

def parse_recipe(site, desired_servings):
    site_code = bs4.BeautifulSoup(site.text, 'html.parser')
    servings = int(site_code.find('span', attrs={
        'class': 'wprm-recipe-servings'}).text)
    output = {'title': site_code.find('h1', attrs={
        'class': 'title'}).text}
    ingredient_list = []
    output['ingredients'] = ingredient_list
    for ingredient in site_code.find_all(
            'li', attrs={'class': 'wprm-recipe-ingredient'}):
        fields = parse_ingredient(ingredient, Fraction(desired_servings, servings))
        ingredient_list.append(fields)
    return output

def format_ingredients(ingredients):
    return ('\n'.join(' - {amount} {unit} {name}'.format(**ingredient)
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', nargs='+')
    parser.add_argument('--servings', type=int, default=6)
    args = parser.parse_args()
    urls = ['https://www.budgetbytes.com/' + url for url in args.url]
    text = format_shopping_list(to_shopping_list(get_recipes(urls, args.servings)))
    print(text)

if __name__ == "__main__":
    main()
