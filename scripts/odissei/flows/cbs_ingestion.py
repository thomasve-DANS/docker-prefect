from prefect import flow
from prefect.deployments import Deployment
from prefect.infrastructure.docker import DockerContainer

from prefect.orion.schemas.states import Completed, Failed
from .tasks.base_tasks import xml2json, dataverse_mapper, \
    dataverse_import, update_publication_date

@flow
def cbs_metadata_ingestion(file_path):
    docker_container_block = DockerContainer.load("docker-agent")
    json_metadata = xml2json(file_path)
    if not json_metadata:
        return Failed(message='Unable to transform from xml to json')
    mapped_metadata = dataverse_mapper(json_metadata)
    if not mapped_metadata:
        return Failed(message='Unable to map metadata')

    import_response = dataverse_import(mapped_metadata)
    if not import_response:
        return Failed(message='Unable to import dataset into Dataverse')

    pid = import_response.json()['data']['persistentId']
    fields = mapped_metadata['datasetVersion']['metadataBlocks']['citation'][
        'fields']
    publication_date = next((field for field in fields if
                            field.get('typeName') == 'distributionDate'), None)
    if publication_date["value"]:
        pub_date_response = update_publication_date(publication_date["value"],
                                                    pid)
        if not pub_date_response:
            return Failed(message='Unable to update publication date')
    else:
        return Completed(message=file_path + " ingested successfully")

def create_deploy():
    deploy = Deployment.build_from_flow(
        flow=cbs_metadata_ingestion,
        name="cbs-ingestion", 
        work_queue_name="demo",
    )
    return deploy

def main():
    if __name__ == '__main__':
        deploy = create_deploy()
        print(deploy)
        deploy.apply()
