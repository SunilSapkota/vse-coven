from flask import Flask, render_template, request, jsonify
from elasticsearch import Elasticsearch

from bs4 import BeautifulSoup
import requests
import time
import re

app = Flask(__name__)

ELASTIC_PASSWORD = "EcdgFUtTNgqgWKtaQOKSzAui"
INDEX_NAME = 'papers'

# Found in the 'Manage Deployment' page
CLOUD_ID = "19e1f485f6104032b7a1850e3c3a8b1d:dXMtY2VudHJhbDEuZ2NwLmNsb3VkLmVzLmlvOjQ0MyQ3NGFiNGVmNGQ3N2M0ZWVkYTFjZGQ4ZjZiZjc3NGI1YyRiZDlhY2QzNjI2NTY0ODUwYWE1ODljODAyYTk5OWRiYg=="

# Create the client instance
es = Elasticsearch(
    cloud_id=CLOUD_ID,
    basic_auth=("elastic", ELASTIC_PASSWORD)
)

# Successful response!
es.info()


# es.indices.delete(index=INDEX_NAME)
if not es.indices.exists(index=INDEX_NAME):
    es.indices.create(index=INDEX_NAME)
else:
    print("")


def get_data_from_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    lis = soup.find_all('li', class_=re.compile('^list-result-item'))

    for li in lis:
        title_element = li.find('h3', class_='title').find('span')
        title = title_element.text if title_element else ''

        authors_element = [author.find('span').text for author in li.find_all('a', class_='link person')]
        authors = authors_element if authors_element else ''

        date_element = li.find('span', class_='date')
        date = date_element.text if date_element else ''

        if not es.exists(index=INDEX_NAME, id=title):
            es.index(index=INDEX_NAME,
                     body={"id": title, "date": date, "authors": authors, "title": title})


@app.route('/suggest', methods=['POST'])
def suggest():
    query = request.form['query']
    body = {
        "query": {
            "match_phrase_prefix": {
                "title": query
            }
        },
        "_source": ["title"],
        "size": 5
    }
    res = es.search(index=INDEX_NAME, body=body)
    titles = [hit['_source']['title'] for hit in res['hits']['hits']]
    return jsonify(titles)


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        query = request.form['search']
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title", "Authors", "Date"]
                }
            }
        }
        res = es.search(index=INDEX_NAME, body=body)
        return render_template('results.html', results=res['hits']['hits'])

    return render_template('search.html')

@app.route('/total', methods=['GET'])
def total():
    body = {
        "query": {
            "match_all": {}
        }
    }
    res = es.search(index=INDEX_NAME, body=body)
    total = res['hits']['total']['value']
    return jsonify(total)

@app.route('/scrape', methods=['GET'])
def scrape():
    url = 'https://pureportal.coventry.ac.uk/en/publications/?format=&page=0'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    last_page_number = int(soup.find('nav', class_='pages').find_all('li')[-2].text.strip())
    count = es.count(index=INDEX_NAME)['count']

    for page_number in range(last_page_number):
        print(f'Scraping page {page_number}')
        url = f'https://pureportal.coventry.ac.uk/en/publications/?format=&page={page_number}'
        get_data_from_page(url)

        # Store scraped data into Elasticsearch
        # for document in data:
        #     es.index(index=INDEX_NAME, doc_type='_doc', body=document)

    return 'Scraping completed'

@app.route('/detail')
def detail():
    title = request.args.get('title')
    # Retrieve the details for the given title from Elasticsearch or perform any other necessary operations
    # You can modify this section based on your specific implementation
    # Example:
    body = {
        "query": {
            "match": {
                "title": title
            }
        }
    }
    res = es.search(index=INDEX_NAME, body=body)
    # Assuming you have a single document matching the title, retrieve the details
    details = res['hits']['hits'][0]['_source']
    return render_template('detail.html', details=details)

if __name__ == '__main__':
    app.run(port=5000)
