"""
Documentation:
    Steps to get this script running:
        1. Create an IBM Watson Studio Machine Learning account / subscription
        2. Generate an API key
        3. Create a deployment space
        4. Create a project and find the project id in IBM Watson Studio Machine Learning
        5. Run the deployment script
    Next Steps:
        1. Check deployment in IBM WML
        2. Continue to the model_execute.py script.
"""
from pathlib import Path
from sample.utils import get_api_key, publish_and_deploy_model

if __name__ == '__main__':
    # set up the credentials:
    wml_credentials = {
        "url": "https://eu-de.ml.cloud.ibm.com",
        "apikey": get_api_key()
    }

    # define which python file contains the optimization model:
    path_to_model = Path('model.py').absolute().__str__()  # can be externalised as part of github automations
    model_name = 'CAR PRODUCTION'  # can be externalised as part of github automations

    # publish and deploy the model:
    publish_and_deploy_model(wml_credentials, path_to_model, model_name,
                             tags=['Sample', 'Opt', 'Cars', 'Produdction'],
                             description="A sample case to optimize the number of cars to produce under capacity constraints.",
                             delete_previous=True)
