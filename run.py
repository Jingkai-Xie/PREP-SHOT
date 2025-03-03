from pyomo.environ import SolverFactory
from pyomo.opt import SolverStatus, TerminationCondition
import configparser
import time
import argparse
# from copt_pyomo import *

from prepshot import load_data
from prepshot import updatedata
from prepshot import create_model
from prepshot import utils

# carbon emission scenario
parser = argparse.ArgumentParser(description='scenario approach')
parser.add_argument('--carbon', type=int, help='carbon emission limits scenario')
parser.add_argument('--price', type=float, default=0.01, help='withdraw water price [RMB/m**3]')
parser.add_argument('--inflow', type=float, default=0, help='inflow scenarios')
parser.add_argument('--demand', type=int, default=0, help='demand scenarios')
parser.add_argument('--invcost', type=int, default=0, help='investment cost scenarios')
args = parser.parse_args()

# default paths
inputpath = './input/'
outputpath = './output/'
logpath = './log/'
logtime = time.strftime("%Y-%m-%d-%H-%M-%S")
logfile = logpath + "main_%s.log"%logtime

utils.write(logfile, "Starting load parameters ...")
start_time = time.time()

# load global parameters
config = configparser.RawConfigParser(inline_comment_prefixes="#")
config.read('global.properties')
basic_para = dict(config.items('global parameters'))
solver_para = dict(config.items('solver parameters'))
hydro_para = dict(config.items('hydro parameters'))

# global parameters
time_length = int(basic_para['hour'])
month = int(basic_para['month'])
dt = int(basic_para['dt'])
# Fraction of One Year of Modeled Timesteps
weight = (month * time_length * dt) / 8760
input_filename = inputpath + basic_para['inputfile']
output_filename = outputpath + basic_para['outputfile']

# hydro parameters
ishydro = bool(int(hydro_para['ishydro']))
error_threshold = float(hydro_para['error_threshold'])
iteration_number = int(hydro_para['iteration_number'])

# solver config
solver = SolverFactory(basic_para['solver'], solver_io='python')
# solver = SolverFactory('copt_direct')
solver.options['TimeLimit'] = int(solver_para['timelimit'])
solver.options['LogToConsole'] = 0
solver.options['LogFile'] = logfile

utils.write(logfile, "Set parameter solver to value %s"%basic_para['solver'])
utils.write(logfile, "Set parameter timelimit to value %s"%int(solver_para['timelimit']))
utils.write(logfile, "Set parameter input_filename to value %s"%input_filename)
utils.write(logfile, "Set parameter output_filename to value %s.nc"%output_filename)
utils.write(logfile, "Set parameter time_length to value %s"%basic_para['hour'])
utils.write(logfile, "Parameter loading completed, taking %s minutes"%(round((time.time() - start_time)/60,2)))

utils.write(logfile, "\n=========================================================")
utils.write(logfile, "Starting load data ...")
start_time = time.time()
# load data
para  = load_data(input_filename, month, time_length)
utils.write(logfile, "Data loading completed, taking %s minutes"%(round((time.time() - start_time)/60,2)))

para['inputpath'] = inputpath
para['time_length'] = time_length
para['month'] = month
para['dt'] = dt
para['weight'] = weight
para['ishydro'] = ishydro
para['logfile'] = logfile

# update parameters according to scenarios (update para)
para['price'] = args.price
para['carbon_scenario'] = (args.carbon, 'carbon_supplementary.xlsx')
para['inflow_scenario'] = (args.inflow, 'inflow.xlsx')
para['hydropower_scenario'] = (args.inflow, 'hydropower.xlsx')
para['invcost_scenario'] = (args.invcost, 'invcost.xlsx')
para['demand_scenario'] = (args.demand, 'demand.xlsx')
para = updatedata(para)

# Validation data
# TODO

# Create a model
utils.write(logfile, "\n=========================================================")
utils.write(logfile, "Start creating model ...")
model = create_model(para)
utils.write(logfile, "Model creating completed, taking %s minutes"%(round((time.time() - start_time)/60,2)))
utils.write(logfile, "\n=========================================================")

# Update output file name by all scenario setting
# output_filename = outputpath +'c%s'%s+ basic_para['outputfile']
output_filename = outputpath + 'c%s'%args.carbon + basic_para['outputfile'] + '_%s'%para['price'] + '%s'%args.inflow + 'demand%s'%args.demand + 'invcost%s'%args.invcost

if para['ishydro']:
    utils.write(logfile, "Start solving model ...")
    start_time = time.time()
    state = utils.run_model_iteration(model, solver, para, iteration_log=logfile,
            error_threshold=error_threshold, iteration_number=iteration_number)
    utils.write(logfile, "Solving model completed, taking %s minutes"%(round((time.time() - start_time)/60,2)))
else:
    utils.write(logfile, "Start solving model ...")
    start_time = time.time()
    results = solver.solve(model, tee=True)
    utils.write(logfile, "Solving model completed, taking %s minutes"%(round((time.time() - start_time)/60,2)))
    if (results.solver.status == SolverStatus.ok) and \
    (results.solver.termination_condition == TerminationCondition.optimal):
        # Do nothing when the solution in optimal and feasible
        state = 0
    elif (results.solver.termination_condition == TerminationCondition.infeasible):
        # Exit programming when model in infeasible
        utils.write(logfile, "Error: Model is in infeasible!")
        state = 1
    else:
        # Something else is wrong
        utils.write(logfile, "Solver Status: ",  results.solver.status)
# print({i:-model.dual[model.emission_limit_cons[i]] for i in [2018,2025,2030,2035,2040,2045,2050]})
if state == 0:
    utils.write(logfile, "\n=========================================================")
    utils.write(logfile, "Start writing results ...")
    utils.saveresult(model, output_filename, ishydro=ishydro)
utils.write(logfile, "Finish!")
