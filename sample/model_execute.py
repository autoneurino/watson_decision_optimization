import logging
import time
from pathlib import Path

import pandas as pd

from sample.model import get_all_inputs
from sample.utils import get_api_key, load_from_disk, get_wml_client, get_solve_parameters


def get_deployment_id():
    settings_path = Path(__file__).parent.parent.joinpath('settings.json')
    settings = load_from_disk(settings_path)
    return settings['deployment_id']


def process_results():
    job_details_do = client.deployments.get_job_details(job_id)
    kpi = job_details_do['entity']['decision_optimization']['solve_state']['details']['KPI.Projected Profit']
    decisions = next(output for output in job_details_do['entity']['decision_optimization']['output_data'] if
                     output["id"] == "solution.csv")
    decision_df = pd.DataFrame(data=decisions['values'], columns=decisions['fields'])
    decision_df.to_csv('solution.csv')
    logging.info(f"projected profit: {kpi}, decisions: {decision_df.to_string()}")


def wait_longer(waited_for_n_seconds: int):
    time.sleep(10)
    waited_for_n_seconds += 10
    return waited_for_n_seconds


def define_job_payload():
    return {
        client.deployments.DecisionOptimizationMetaNames.INPUT_DATA: [
            {
                "id": "Availability.csv",
                "values": inputs['Availability']
            },
            {
                "id": "ProductInfo.csv",
                "values": inputs['ProductInfo']
            }
        ],
        client.deployments.DecisionOptimizationMetaNames.OUTPUT_DATA: [
            {
                "id": ".*.csv"
            }
        ]
    }


if __name__ == '__main__':
    # get inputs:
    inputs = get_all_inputs()

    solve_parameters = get_solve_parameters()
    # set up the credentials:
    wml_credentials = {
        "url": "https://eu-de.ml.cloud.ibm.com",
        "apikey": get_api_key()
    }

    client = get_wml_client(wml_credentials)

    deployment_id = get_deployment_id()

    job_payload_ref = define_job_payload()

    job = client.deployments.create_job(deployment_id, meta_props=job_payload_ref)
    job_id = client.deployments.get_job_uid(job)

    elapsed_time = 0
    while client.deployments.get_job_status(job_id).get('state') != 'completed' and elapsed_time < 300:
        elapsed_time = wait_longer(elapsed_time)
    if client.deployments.get_job_status(job_id).get('state') == 'completed':
        process_results()
    else:
        print("Job hasn't completed successfully in 5 minutes.")
