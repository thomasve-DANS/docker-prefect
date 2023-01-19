from dynaconf import Dynaconf
from prefect import flow

from tasks.oaiore_to_x3ml_tasks import get_pids, save_pids, save_metadatas_oaiore, zip_folder, transform, \
     load

settings = Dynaconf(settings_files=["conf/settings.toml", "conf/.secrets.toml"],
                    environments=True)

def get_headers(api_token):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json',
    }
    return headers

@flow
def ariadne_flow():
    pids = get_pids(settings)
    pids_file = save_pids(settings, pids)
    oaiore_dir_name = save_metadatas_oaiore(settings, pids_file)
    x3ml_dir_name = transform(settings.TRANSFORMER_URL, get_headers(settings.DANS_TRANSFORMER_SERVICE_API_KEY), oaiore_dir_name)
    zip_result = zip_folder(x3ml_dir_name)
    load(settings, zip_result)
