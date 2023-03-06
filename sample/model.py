import logging
import os
import sys
from os.path import splitext
from typing import Dict, Union

import pandas as pd
from docplex.cp.model import CpoModel
from docplex.mp.model import Model
from docplex.util.environment import get_environment
from six import iteritems


def get_all_inputs() -> Dict:
    """
    This function reads all available input .csv from a job for a deployment.

    If developing locally, place your .csv file in the same location as this script. If you want to use other sources
    than .csv (e.g. SQL server, tm1, api requests) in your execution, perform these steps:
     - load data on server/pc that is going to create jobs for Watson with e.g. SQL, mdx, api requests etc.
     - transform the data to desired format, e.g. pd.DataFrame.
     - create a job for watson with:
        - ibm_watson_machine_learning.APIClient.deployments.DecisionOptimizationMetaNames.INPUT_DATA

    :return: inputs: dictionary of file_names with pandas DataFrame objects as value
    """

    result = {}

    env = get_environment()  # gets a docplex environment to replicate an execution environment.

    # loops through all files in root directory and retrieves all files with extension '.csv'.
    csv_files = [file_name for file_name in os.listdir('.') if splitext(file_name)[1] == '.csv']

    for file_name in csv_files:
        with env.get_input_stream(file_name) as in_stream:
            df = pd.read_csv(in_stream)  # reads the csv content in a pandas dataframe
            dataset_name, _ = splitext(file_name)  # gets the file name without extension
            result[dataset_name] = df  # stores the content in a dictionary
    return result


def create_base_model(inputs: Dict[str, pd.DataFrame]):
    """
    This function creates the model to
    :param inputs: A dictionary of pandas dataframes containing the required input data to build variables, constraints,
                   and objectives.
    :return: docplex.mp.model.Model object; the fully formulated and optimized mathematical program. Includes:
             variables, constraints, objective function, solution, (kpis)
    """
    requirement = inputs['ProductInfo'].set_index('ResourceName')  # defines requirements to build cars
    availability = inputs['Availability'].set_index('Resource')  # defines availability of resources to build cars

    model = Model(name='car_production')  # init model

    # by default, all variables in Docplex have a lower bound of 0 and infinite upper bound.
    # We use the key_format argument to separate the variable name and the variable instance name i.e:
    # (QtyToProduce__CAR1, QtyToProduce__CAR2). This allows us to separate variables based on their name safely
    # in a later stage.
    material_qty_to_produce = model.continuous_var_dict(keys=list(requirement.index.values),
                                                        name='QtyToProduce',
                                                        key_format='__%s')
    # we create slack variables to track model infeasibility, in this case we want to optimize profit under the
    # constraint of producing more than required given the available resources. If we cannot produce all requirements
    # given the resources at hand, we still want a optimal solution for those resoures that we can produce.
    # In such case, we give the model some slack. This enables us to report on the used slack which represents the
    # unfulfilled demand.
    slacks = model.continuous_var_dict(keys=requirement.index, name='UnfulfilledDemand', key_format='__%s')

    # CONSTRAINTS
    # constraint #1: production >= demand
    for m in material_qty_to_produce:
        model.add_constraint(
            material_qty_to_produce[m] + slacks[m] >= requirement.loc[m, 'RequiredThisWeek'])

    # constraint #3: total assembly time limit
    assembly_constraint = model.add_constraint(
        model.sum(requirement.loc[m, 'AssemblyHours'] * material_qty_to_produce[m] for m in material_qty_to_produce) <=
        availability.loc['Assembly', 'Capacity'])

    # constraint #4: painting time limit
    painting_constraint = model.add_constraint(
        model.sum(requirement.loc[m, 'PaintingHours'] * material_qty_to_produce[m] for m in material_qty_to_produce) <=
        availability.loc['Painting', 'Capacity'])

    # objective
    projected_profit = model.sum(
        requirement.loc[m, 'ProfitMargin'] * material_qty_to_produce[m] for m in material_qty_to_produce)

    # constraint to consolidate the total unfulfilled demand -> makes unfulfilled_demand kpi easier to read.
    unfulfilled_demand = model.sum(slacks[m] for m in material_qty_to_produce)

    # we add some KPIs to keep track of, cplex will include the values of these in the output after solving.
    model.add_kpi(projected_profit, publish_name="Projected Profit")
    model.add_kpi(unfulfilled_demand, publish_name="Unfulfilled Demand")

    # this purely states the objective is to maximize the projected_profit, it does not start the solve:
    model.maximize(projected_profit)

    return model


def solve_model(model: Model):
    """
    :param model: starts the model solve.
    :return: model after solving attempt, may be infeasible, optimal or partially solved.
    """
    status = model.solve()
    return model


def parse_solution(model: Union[Model, CpoModel]) -> Dict[str, pd.DataFrame]:
    """
    We extract the solution from the Model object.

    Warning: in case there are variables from different dimension, this function will create a very sparse solution_df
    dataframe.

    :param model: a docplex mp Model (could be extended with support for CpoModels).
    :return: ouputs a dictionary of pandas dataframes with solution variables, kpis and potentially other interesting
             information.
    """
    solution_df = pd.DataFrame()  # initialize a dataframe

    # loop through all decision variables and split based on the key_format (see create model -> variable creation)
    # string before split is the variable name, string after split is the instance.
    for _, dvar in enumerate(model.solution.iter_variables()):
        col, row = dvar.to_string().split('__')
        solution_df.loc[row, col] = dvar.solution_value

    outputs = {'solution': solution_df,
               'kpis': pd.DataFrame(model.kpis_as_dict(), index=[0])
               }
    return outputs


def outputs_to_csv(outputs: Dict[str, pd.DataFrame]):
    """
    Writes all dataframes in outputs to .csv format. The name of the csv will be the key in the dictionary. These csvs
    will also be what job instances will return in json format, e.g.:

    {"output_data":
        [
        {
        "fields": ["Name", "Value"],
        "id": "kpis.csv",
        "values": [["Projected Profit", 71200],
                  ["Unfulfilled Demand", 116]]
        },
        {
        "fields": ["Name", "Value"],
        "id": "stats.csv",
        "values": [["cplex.modelType", "LP"],
                   ["cplex.size.integerVariables", 0],
                   ["cplex.size.continousVariables", 12],
                   ["cplex.size.linearConstraints", 8],
                   ["cplex.size.booleanVariables", 0],
                   ["cplex.size.constraints", 8],
                   ["cplex.size.quadraticConstraints", 0],
                   ["cplex.size.variables", 12],
                   ["job.coresCount", 1],
                   ["job.inputsReadMs", 95],
                   ["job.memoryPeakKB", 111916],
                   ["job.modelProcessingMs", 1420]]
        },
        {
        "fields": ["QtyToProduce", "UnfulfilledDemand"],
          "id": "solution.csv",
          "values": [[800, null],
          [1600, null],
          [null, 50],
          [null, 43],
          [null, 11],
          [null, 12]]
          }
        ]
        }

    :param outputs: the dictionary of pandas dataframes.
    """
    for (name, df) in iteritems(outputs):
        csv_file = f'{name}.csv'
        print(csv_file)
        with get_environment().get_output_stream(csv_file) as fp:
            if sys.version_info[0] < 3:
                fp.write(df.to_csv(index=False, encoding='utf8'))
            else:
                fp.write(df.to_csv(index=False).encode(encoding='utf8'))
    if len(outputs) == 0:
        logging.warning('No outputs written')


if __name__ == '__main__':
    input_files = get_all_inputs()
    model_formulation = create_base_model(input_files)
    solved_model = solve_model(model_formulation)
    output_files = parse_solution(solved_model)
    outputs_to_csv(output_files)
