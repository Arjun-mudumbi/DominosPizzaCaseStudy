import geopy
import csv
import sqlite3
from gurobipy import *
import pandas as pd
#%% import distributionc center data
DistributionCenter={}
with open("distributionCenter.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        DistributionCenter[row[0].replace(" ","")] = (float(row[1]), float(row[2]))
        
#%%%% importing the supply demand of distribution center from the csv file
supplydata={}
with open("supplydata.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        supplydata[row[0].replace(" ","")] = (float(row[1]), float(row[2])) 
#%%
distance={}
from geopy.distance import vincenty
for st in supplydata:
    for dc in DistributionCenter:
        distance[(st,dc)]=vincenty(supplydata[st],DistributionCenter[dc]).miles         
#%%%% importing the supply capacity of supplier from the csv file
supply={}
with open("supply.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        supply[row[0].replace(" ","")] = int(4.0*int(row[1])/7) 
#%%%
demand={}
with open("demand.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        demand[row[0].replace(" ","")] = int(row[1])
#%% import cost function
supplierstate={}
with open("supplierstate.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        supplierstate[row[0].replace(" ","")] = str(row[1])    
#%%Supplier Running cost
opcost={}
with open("supplier_op.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        opcost[row[0].replace(" ","")] = int(row[1])         

     
#%%supplier cost
gencost={}
with open("cost.csv", "r") as myCSV:
    myReader = csv.reader(myCSV)
    for row in myReader:
        gencost[row[0].replace(" ","")] = (float(row[1]))        
#%%
Midwest=["MI","MO","MN","IA","IL","IN","KS","NE","ND","OH","SD","WI"]
Southeast=["KY","GA","FL","AL","DC","MS","NC","SC","TN","WV","VA"]
Northeast=["MD","NC","CT","DE","MA","ME","NH","NJ","NY","PA","RI","VT"]
Southwest=["LA","TX","OK"]
West=["CO","AZ","WA","CA","AR","ID","AK","HI","MT","NV","NM","OR","UT","WY"]
#%%Assigning distribution cost            
distcost={}

for st in supplierstate:
        if supplierstate[st] in Midwest:
            distcost[st]= 1.64;
        elif supplierstate[st] in Southeast:
            distcost[st]= 1.68;
        elif supplierstate[st] in Southwest:
            distcost[st]= 1.67;
        elif supplierstate[st] in Northeast:
            distcost[st]= 1.79;
        elif supplierstate[st] in West:
            distcost[st]= 1.77;
        else:
            distcost[st]=100000000            
        
#%% Create the model
charpizza = Model()
charpizza.modelSense = GRB.MINIMIZE
charpizza.update()
#%% create the variables

# create a dictionary that will contain the gurobi variable objects
mypizza = {}
for st in supplydata:
    for dc in DistributionCenter:
        mypizza[st,dc] = charpizza.addVar(obj = ( ( distcost[st]*distance[st,dc]*demand[dc] )/880 + ( demand[dc]*gencost[st] ) ), 
                                   vtype = GRB.BINARY, 
                                   name = 'x_%s_%s' % ([st,dc][1], [st,dc][0]))
charpizza.update()
#%%
rc_mill = {}
for st in supplydata:
    VarName = 'running_cost_%s' %st
    rc_mill[st] = charpizza.addVar(obj = opcost[st], vtype = GRB.BINARY, name = VarName)
charpizza.update()    
#%% create the supply constraints
myConstrs = {}
for st in supplydata:
    constrName = 'supply'
    myConstrs[constrName] = charpizza.addConstr(quicksum(mypizza[st,dc]*demand[dc] for dc in DistributionCenter) 
                                               <= supply[st]*rc_mill[st], name = constrName)
charpizza.update()
#%%create the demand constrain
for dc in DistributionCenter:
    constrName = 'demand' 
    myConstrs[constrName] = charpizza.addConstr(lhs=(quicksum(mypizza[st,dc] for st in supplydata)),sense = GRB.EQUAL,
             rhs = 1, name = constrName)
charpizza.update()
    
#%%% create non negativity constrains
for st in supplydata:
    for dc in DistributionCenter:
        constrName = 'nonnegatavity'
        myConstrs[constrName] = charpizza.addConstr(mypizza[st,dc] 
                                               >=0 , 
                                               name = constrName)
charpizza.update()
    
    
#%% write the model to the directory and solve it
charpizza.setParam('MIPFocus',1)
charpizza.setParam('MIPGap',0.2)
charpizza.write('test.lp')
charpizza.optimize()

#%% print the solution to the screen
if charpizza.Status == GRB.OPTIMAL:
 for st in supplydata:    
    for dc in DistributionCenter:
            if mypizza[st,dc].x > 0:
                print( st,dc, mypizza[st,dc].x*demand[dc])
                
        
#%% save results in a database
if charpizza.Status == GRB.OPTIMAL:
    myConn = sqlite3.connect('charPizza.db')
    myCursor = myConn.cursor()
    pizzaSol = []
    for st in supplydata:
        for dc in DistributionCenter:
            if mypizza[st,dc].x > 0:
                pizzaSol.append((st,dc, mypizza[st,dc].x))
                     

    # create the table    
    sqlString = """
                CREATE TABLE IF NOT EXISTS tblPizza
                (Supplier      TEXT,
                 Distribution Center           TEXT,
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
#%%
print(charpizza.ObjVal)