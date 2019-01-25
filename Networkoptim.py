import geopy
import csv
import sqlite3
from gurobipy import *
import pandas as pd

#%%%%%%% import stores data 
stores={}
with open("store.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        stores[row[0]] = (float(row[1]), float(row[2]))



#%%%%%%% import distributionc center data
DistributionCenter={}
with open("distributioncenter.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        DistributionCenter[row[0]] = (float(row[1]), float(row[2]))
#%%%%%%%% Caluclating the distance from distribution center to store
distance={}
from geopy.distance import vincenty
for st in stores:
    for dc in DistributionCenter:
        distance[(dc,st)]=vincenty(DistributionCenter[dc],stores[st]).miles
        
#%%%% importing the supply from the csv file
supply={}
with open("supply.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        supply[row[0]] = int(4.0*int(row[1])/7)
#%% import demand from the csv file
demand ={}
with open("demand.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        demand[row[0]] = int(4*float(row[1]))

#%% import cost function
distributionstate={}
with open("distributionCenterstate.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        distributionstate[row[0]] = str(row[1])

#%%
Midwest=["MI","MO","MN","IA","IL","IN","KS","NE","ND","OH","SD","WI"]
Southeast=["KY","GA","FL","AL","DC","MS","NC","SC","TN","WV"]
Northeast=["MD","NC","CT","DE","MA","ME","NH","NJ","NY","PA","RI","VT"]
Southwest=["LA","TX","OK"]
West=["CO","AZ","WA","CA","AR","ID","AK","HI","MT","NV","NM","OR","UT","WY"]
#%%%
cost={}

for ds in distributionstate:
        if distributionstate[ds] in Midwest:
            cost[ds]= 1.64;
        elif distributionstate[ds] in Southeast:
            cost[ds]= 1.68;
        elif distributionstate[ds] in Southwest:
            cost[ds]= 1.67;
        elif distributionstate[ds] in Northeast:
            cost[ds]= 1.79;
        elif distributionstate[ds] in West:
            cost[ds]= 1.77;
        else:
            cost[ds]=100000000
            
        
#%% Create the model
charpizza = Model()
charpizza.modelSense = GRB.MINIMIZE
charpizza.update()

#%% create the variables

# create a dictionary that will contain the gurobi variable objects
mypizza = {}
for dc in supply:
    for st in stores:
        mypizza[dc,st] = charpizza.addVar(obj = ( cost[dc]*distance[dc,st]*demand[st] )/9900, 
                                   vtype = GRB.BINARY, 
                                   name = 'x_%s_%s' % ([dc,st][1], [dc,st][0]))
charpizza.update()

#%% create the supply constraints
myConstrs = {}
for dc in DistributionCenter:
    constrName = 'supply'
    myConstrs[constrName] = charpizza.addConstr(quicksum(mypizza[dc,st]*demand[st] for st in stores) 
                                               <= supply[dc], name = constrName)
charpizza.update()
#%%create the demand constrain
for st in stores:
    constrName = 'demand' 
    myConstrs[constrName] = charpizza.addConstr(lhs=quicksum((mypizza[dc,st]*demand[st] for dc in DistributionCenter)), 
                                               sense=GRB.EQUAL,rhs=demand[st], name = constrName)
charpizza.update()
    
#%%% create non negativity constrains
for dc in DistributionCenter :
    for st in stores:
        constrName = 'nonnegatavity'
        myConstrs[constrName] = charpizza.addConstr(mypizza[dc,st] 
                                               >=0 , 
                                               name = constrName)
charpizza.update()
    
    
#%% write the model to the directory and solve it
charpizza.setParam('MIPFocus',1)
charpizza.setParam('MIPGap',0.001)
charpizza.write('test.lp')
charpizza.optimize()

#%% print the solution to the screen
if charpizza.Status == GRB.OPTIMAL:
    for dc in DistributionCenter:
        for st in stores:
            if mypizza[dc,st].x > 0:
                print( dc,st, mypizza[dc,st].x*demand[st])
                
        
#%% save results in a database
if charpizza.Status == GRB.OPTIMAL:
    myConn = sqlite3.connect('charPizza.db')
    myCursor = myConn.cursor()
    pizzaSol = []
    for dc in DistributionCenter:
        for st in stores:
            if mypizza[dc,st].x > 0:
                pizzaSol.append((dc,st, mypizza[dc,st].x* demand[st]))

    # create the table    
    sqlString = """
                CREATE TABLE IF NOT EXISTS tblPizza
                (Distribution Center      TEXT,
                 Store           INT,
                 QTY            DOUBLE);
                """
    myCursor.execute(sqlString)
    myConn.commit()
    
    # create the insert string
    sqlString = "INSERT INTO tblPizza VALUES(?,?,?);"
    myCursor.executemany(sqlString, pizzaSol)    
    myConn.commit()
            
    myCursor.close()
    myConn.close()
#   
    print(charpizza.ObjVal)