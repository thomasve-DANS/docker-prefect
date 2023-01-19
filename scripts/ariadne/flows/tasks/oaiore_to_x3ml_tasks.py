# 1) process = get dccd Pids
# result = pids.txt file with a pid on each line
# 2) process = get metadata OAI_ORE
# result = collection of metadata json files
# 3) process = transform json to xml (no default ns)
# result = collection of metadata xml files
# 4) process = transport files to ARIADNE
import datetime
import json
import logging
import os

import requests

import shutil
import datetime
from minio import Minio

import requests
from prefect import task

# Code from Paul Boon.
def search(server_url, subtree, start=0, rows=0):
    '''
    Do a query via the public search API, only published datasets
    using the public search 'API', so no token needed

    Note that the current functionality of this function is very limited!

    :param subtree: This is the collection (dataverse alias)
                    it recurses into a collection and its children etc. very useful with nesting collection
    :param start: The cursor (zero based result index) indicating where the result page starts
    :param rows: The number of results returned in the 'page'
    :return: The 'paged' search results in a list of dictionaries
    '''

    # always type=dataset, those have pids (disregarding pids for files)
    params = {
        'q': '*',
        'subtree': subtree,
        'type': 'dataset',
        'per_page': str(rows),
        'start': str(start)
    }

    # params['fq'] = ''

    dv_resp = requests.get(server_url + '/api/search', params=params)

    # give some feedback
    # print("Status code: {}".format(dv_resp.status_code))
    # print("Json: {}".format(dv_resp.json()))
    # the json result is a dictionary... so we could check for something in it
    dv_resp.raise_for_status()
    resp_data = dv_resp.json()['data']
    # print(json.dumps(resp_data, indent=2))
    return resp_data


def get_pids(settings):
    total_count = 1
    rows = 100
    start = 0
    page = 1
    pids = []
    while start < total_count:
        result = search(settings.DATAVERSE_URL, settings.DV_NAME, start, rows)
        total_count = result['total_count']
        for i in result["items"]:
            pids.append(i['global_id'])
        start = start + rows
        page += 1
    return pids

def save_pids(settings, pids):
    #TODO: Logging and exception
    pids_file = settings.OUTPUT_DIR + '/pids-' + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    with open(pids_file, 'w') as fp:
        fp.write('\n'.join(pids))
    return pids_file


def get_metadata_oaiore(settings, pid):
    params = {
        'exporter': 'OAI_ORE',
        'persistentId': pid,
    }
    dv_resp = requests.get(settings.DATAVERSE_URL + '/api/datasets/export', params)
    #TODO logging and error handling
    return dv_resp.text


def save_metadatas_oaiore(settings, pids_file):
    oaiore_dir = settings.OUTPUT_DIR + "/oaiore-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    os.mkdir(oaiore_dir)
    with open(pids_file) as fp:
        pids = fp.readlines()
        for pid in pids:
            oaiore_filename = oaiore_dir + "/" + pid.replace(':', '_').replace('/', '_').strip() + '.json'
            oaiore = get_metadata_oaiore(settings, pid)
            with open(oaiore_filename, 'w') as fp:
                fp.write(oaiore)

    return oaiore_dir


def zip_folder(x3ml_dir_name):
    # name with dates
    zip_name = os.path.basename(os.path.normpath(x3ml_dir_name))
    zip_target = os.path.dirname(x3ml_dir_name)
    zip_location = shutil.make_archive(zip_target + "/" + zip_name, format='zip', root_dir=x3ml_dir_name)
    return zip_location


def send_simple_message(settings, mail_text, attached_file):
    return requests.post(
        settings.MAIL_API_URL,
        auth=("api", settings.MALI_API_KEY),
        files=[("attachment", attached_file)],
        data={"from": settings.MAIL_FROM,
              "to": [settings.MAIL_TO],
              "subject": settings.MAIL_SUBJECT,
              "text": mail_text})


@task(name="Extract Pids", retries=3, retry_delay_seconds=120)
def extract(settings) -> dict:
    pids = get_pids(settings)
    pids_file = save_pids(settings, pids)
    dir_name = save_metadatas_oaiore(settings, pids_file)
    return dir_name


@task(name="Transform oai-ore")
def transform(transformer_url, headers, oaiore_dir_name: str):
    x3ml_dir_name = oaiore_dir_name + "-transformed"
    os.mkdir(x3ml_dir_name)
    logging.debug('Start transforming json ore to xml.')
    for filename in os.listdir(oaiore_dir_name):
        if filename.endswith(".json"):
            logging.debug(filename)  # logging.debuging file name of desired extension
            with open(os.path.join(oaiore_dir_name, filename), "r") as f:
                f_json = json.load(f)
                logging.debug(f"Transform {filename}.")
                transformer_response = requests.post(transformer_url, headers=headers,
                                                     data=json.dumps(f_json))
                if transformer_response.status_code != 200:
                    print(f"ERROR status code: {transformer_response.status_code}")
                    logging.error(f"Error response from transformer with error code {transformer_response.status_code}")
                else:
                    # print(transformer_response.content)
                    resp_data = transformer_response.json()['result']
                    with open(os.path.join(x3ml_dir_name, filename.replace(".json", ".xml")),
                              "w") as transformed_file:
                        transformed_file.write(resp_data)
        else:
            continue
    logging.debug('End transformation.')
    return x3ml_dir_name

@task(retries=3, retry_delay_seconds=120)
def load(settings, x3ml_zip_name):
    # Create client with access and secret key.
    client = Minio(settings.DANS_MINIO_ENDPOINT, settings.DANS_MINIO_ACCESS_KEY, settings.DANS_MINIO_SECRET_KEY)
    # buckets = client.list_buckets()
    if client.bucket_exists(settings.DANS_MINIO_BUCKET):
        print(f"{settings.DANS_MINIO_BUCKET} exists")
        filename = os.path.basename(x3ml_zip_name)
        client.fput_object(settings.DANS_MINIO_BUCKET, filename, x3ml_zip_name)
    else:
        print(f"{settings.DANS_MINIO_BUCKET} does not exist")