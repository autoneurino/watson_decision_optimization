# Watson Studio Decision Optimization

This repo consists of a sample that shows how to orchestrate decision optimization model development, deployment, and
execution from Python.

Pre-requisites:

1. Watson Studio Account - Pay as you go (first ~200 euro free) https://cloud.ibm.com/registration
2. Watson Studio API key https://cloud.ibm.com/iam/apikeys
3. A Watson Deployment Space https://www.ibm.com/docs/en/cloud-paks/cp-data/4.6.x?topic=spaces-creating-deployment or
   you can also do this with Python http://ibm-wml-api-pyclient.mybluemix.net/core_api.html#client.Deployments after
   getting your **api key**
4. A settings.json & an auth.json in the root of this project.

### API Key

Create your api keys here: https://cloud.ibm.com/iam/apikeys
Make sure to store the api key in your key vault (keepass orso). You cannot view your API after creation and will
have to create a new one in case you've lost it.

### settings.json & auth.json

The settings.json file contains the relevant Watson account dependent information. All you need to get started is a
space_uid. Add a settings.json to the root of this project in this format:

{
"space_uid": "YOUR SPACE UID HERE"
}

You can find your space_uid here: https://<LOCATION>.dataplatform.cloud.ibm.com/ml-runtime/spaces
Also add an auth.json file in this format:

{
"api_key": "YOUR KEY HERE"
}

### Process

1. Create a decision optimization model with docplex in Python.
2. Publish & Deploy the model
3. Create jobs for the model to execute on demand

#### DO Model - _model.py_

The DO model will likely need input to formulate constraints, variables, objectives and possibly run configurations
dynamically. It will also need outputs which will be returned by job instances.

#### Deployment - _model_deploy.py_

The deployment of the model simply puts the DO Model in the IBM Watson cloud and ensures it can be executed with a given
hardware and software specification. You can see the publication of the model as the definition of software specs
whereas the deployment represents the binding to hardware specs for operationalization.

#### Jobs & Execution - _model_execute.py_

After a model is deployed it can be called. In model_execute.py, we show how jobs can be created for a deployed DO
model. The execution python script can be run on demand e.g. when a used clicks a button in a front-end software. The
python script will collect all required inputs transform then to dataframes and pass them to the deployed model as part
of the job specifications.
