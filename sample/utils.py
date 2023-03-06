import datetime
import json
import logging
import os
import pickle
import tarfile
from json import JSONDecodeError
from os.path import splitext
from pathlib import Path
from typing import Dict, List

from ibm_watson_machine_learning import APIClient


def load_from_disk(file_name: Path):
    if file_name.__str__()[-4:] == '.pkl':
        with open(file_name, 'rb') as f:
            return pickle.load(f)

    elif file_name.__str__()[-5:] == '.json':
        with open(file_name, 'r') as f:
            return json.load(f)


def write_to_disk(obj, file_name):
    name, extension = splitext(file_name)
    if extension == '.json':
        with open(file_name, 'w') as f:
            json.dump(obj, f)
    else:
        raise NotImplementedError(f'{extension} not implemented.')


def get_spaces(client: APIClient):
    return client.spaces.list(limit=10)


def get_solve_parameters():
    # can be replaced with solve parameters retrieval from e.g. tm1.
    return {
        "oaas.logAttachmentName": "log.txt",
        "oaas.logTailEnabled": "true",
        "oaas.timeLimit": 10,
        "oaas.resultsFormat": "JSON",  # Enum: JSON, CSV, XML, TEXT, XLSX
        "oaas.dumpZipName": True,
        "oaas.dumpZipRules": """(duration>=1000)
                                 or (&amp;(duration&lt;1000)(!(solveState.solveStatus=OPTIMAL_SOLUTION)))
                                 or (|(solveState.interruptionStatus=OUT_OF_MEMORY)
                                (solveState.failureInfo.type=INFRASTRUCTURE))"""
    }


def get_api_key() -> str:
    """
    Executes:
        Returns your api key given it is in a auth.json file in the directory.

    Info:
        Create your api keys here: https://cloud.ibm.com/iam/apikeys
        Make sure to store the api key in your key vault (keepass orso). You cannot view your API after creation and will
        have to create a new one in case you've lost it.

    Warning:
        Do not commit the auth.json to any version control software.

    :return: api_key: str
    """

    auth_path = Path(__file__).parent.parent.joinpath('auth.json')

    file_structure = '{"api_key": "API_KEY_HERE"}'
    file_structure_error_msg = f'Please provide the auth.json in the following structure: {file_structure}'
    file_missing_error_msg = 'Please place the auth.json file in the root of project directory.'
    try:
        api_key = load_from_disk(auth_path)['api_key']
    except FileNotFoundError as e:
        logging.exception(e)
        raise FileNotFoundError(file_missing_error_msg)
    except (JSONDecodeError, KeyError) as e:
        logging.exception(e)
        raise KeyError(file_structure_error_msg)

    return api_key


def get_project_id() -> str:
    """
    Executes:
        Returns your project_id given it is in a settings.json file in the directory.

    Info:
        Create your project id in the WML project of interest.

    Warning:
        You can commit the settings.json, but since this is environment dependent we advise against it.

    :return: project_id: str
    """

    settings_path = Path(__file__).parent.parent.joinpath('settings.json')

    file_structure = '{"project_id": "PROJECT_ID_HERE"}'
    file_structure_error_msg = f'Please provide the settings.json in the following structure: {file_structure}'
    file_missing_error_msg = 'Please place the settings.json file in the root of project directory.'
    try:
        project_id = load_from_disk(settings_path)['project_id']
    except FileNotFoundError as e:
        logging.exception(e)
        raise FileNotFoundError(file_missing_error_msg)
    except (JSONDecodeError, KeyError) as e:
        logging.exception(e)
        raise KeyError(file_structure_error_msg)

    return project_id


def get_space_uid() -> str:
    """
    Executes:
        Returns your space_uid given it is in a settings.json file in the directory.

    Info:
        Create your space in wml and get the space uid in https://eu-de.dataplatform.cloud.ibm.com/ml-runtime/spaces

    Warning:
        You can commit the settings.json, but since this is environment dependent we advise against it.

    :return: space_uid: str
    """

    settings_path = Path(__file__).parent.parent.joinpath('settings.json')

    file_structure = '{"space_uid": "SPACE_UID"}'
    file_structure_error_msg = f'Please provide the settings.json in the following structure: {file_structure}'
    file_missing_error_msg = 'Please place the settings.json file in the root of project directory.'
    try:
        space_uid = load_from_disk(settings_path)['space_uid']
    except FileNotFoundError as e:
        logging.exception(e)
        raise FileNotFoundError(file_missing_error_msg)
    except (JSONDecodeError, KeyError) as e:
        logging.exception(e)
        raise KeyError(file_structure_error_msg)

    return space_uid


def publish_and_deploy_model(wml_credentials: Dict, model_python_path: str, model_name: str = 'OPTIMIZATION MODEL',
                             tags: List[str] = None, description='An optimization model.',
                             delete_previous: bool = False):
    """
    :param wml_credentials:
    :param model_name:
    :param model_python_path:
    :param tags:
    :param description:
    :param delete_previous:
    :return:
    """
    client = get_wml_client(wml_credentials)
    model_publication_name_plus_date = f"{model_name} PUBLICATION- {datetime.datetime.today().strftime('%Y-%m-%d')}"
    model_deployment_name_plus_date = f"{model_name} DEPLOYMENT - {datetime.datetime.today().strftime('%Y-%m-%d')}"

    if delete_previous:
        delete_previous_publication_and_deployment(client)

    published_model_id = publish(client, model_publication_name_plus_date, model_python_path)
    store_publishing_id(published_model_id)

    deployment_id = deploy(client, published_model_id, model_deployment_name_plus_date, tags, description)
    store_deployment_id(deployment_id)


def delete_previous_publication_and_deployment(client):
    delete_previous_deployment(client)
    delete_previous_publication(client)


def delete_previous_deployment(client):
    try:
        previous_deployed_model_id = get_deployment_id()
        client.deployments.delete(previous_deployed_model_id)
    except Exception as e:
        logging.exception(e)
        pass


def delete_previous_publication(client):
    try:
        previous_published_model_id = get_publish_id()
        client.repository.delete(previous_published_model_id)
    except Exception as e:
        logging.exception(e)
        pass

def store_deployment_id(deployment_id):
    settings, settings_path = get_settings()
    settings['deployment_id'] = deployment_id
    write_to_disk(settings, settings_path)


def get_publish_id():
    settings, _ = get_settings()
    return settings['publishing_id']


def get_deployment_id():
    settings, _ = get_settings()
    return settings['deployment_id']


def store_publishing_id(deployment_id):
    settings, settings_path = get_settings()
    settings['publishing_id'] = deployment_id
    write_to_disk(settings, settings_path)


def get_settings():
    settings_path = Path(__file__).parent.parent.joinpath('settings.json')
    settings = load_from_disk(settings_path)
    return settings, settings_path


def get_wml_client(wml_credentials):
    space_uid = get_space_uid()
    client = APIClient(wml_credentials)  # authenticate to wml
    client.set.default_space(space_uid=space_uid)
    return client


def publish(client: APIClient, model_name, model_python_path):
    # zip the model in gz.tar
    model_zip_path = zip_model(model_python_path, model_name)
    model_meta_props = specify_model_meta_properties(client, model_name)
    published_model = client.repository.store_model(model=model_zip_path, meta_props=model_meta_props)
    published_model_id = client.repository.get_model_id(published_model)
    return published_model_id


def deploy(client: APIClient, published_model_id, deployment_name: str, tags: List[str], description: str,
           hardware_spec=None):
    if hardware_spec is None:
        hardware_spec = {"name": "S", "num_nodes": 1}

    meta_data = {
        client.deployments.ConfigurationMetaNames.NAME: f"{deployment_name}",
        client.deployments.ConfigurationMetaNames.BATCH: {},
        client.deployments.ConfigurationMetaNames.HARDWARE_SPEC: hardware_spec,
        client.deployments.ConfigurationMetaNames.DESCRIPTION: description,
        client.deployments.ConfigurationMetaNames.TAGS: tags}
    deployment_details = client.deployments.create(published_model_id, meta_props=meta_data)

    deployment_id = client.deployments.get_id(deployment_details)

    return deployment_id


def specify_model_meta_properties(client: APIClient, model_name):
    # publish model
    software_spec_uid = client.software_specifications.get_uid_by_name("do_22.1")
    model_meta_props = {
        client.repository.ModelMetaNames.NAME: model_name,
        client.repository.ModelMetaNames.TYPE: "do-docplex_22.1",
        client.repository.ModelMetaNames.SOFTWARE_SPEC_UID: software_spec_uid}
    return model_meta_props


def zip_model(path_to_python_model: str, model_name: str):
    os.makedirs(name=model_name, exist_ok=True)
    path_to_zip = f"{model_name}/model.tar.gz"
    with tarfile.open(path_to_zip, "w:gz") as tar:
        tar.add(path_to_python_model, arcname=os.path.basename(path_to_python_model))

    return path_to_zip
