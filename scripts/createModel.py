#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script name: createModel.py
Created on Wed. 08/7/2024
Author: Arnab Mutsuddy (edited by JRH)

Description: This script reads in the input files for the model and creates 
            an Antimony model file, which is then converted to SBML format. The SBML 
            model is then compiled using the AMICI package. The script requires the 
            following input files: Compartments.txt, Species.txt, StoicMat.txt, 
            Ratelaws.txt, and Observables.txt. The script also requires the Antimony 
            package to be installed. The script outputs a file called ParamsAll.txt, 
            which lists all parameter names, reaction names, and values. The script 
            also outputs an SBML file called SPARCED.xml, which is used to compile the 
            model using the AMICI package. The script also outputs a folder called SPARCED, 
            which contains the compiled model code. The script also annotates the SBML 
            model with information from the input files. The script also defines 
            observables for the model

Output: ParamsAll.txt, SPARCED.txt, SPARCED.xml, SPARCED folder
"""

#-----------------------Package Import & Defined Arguements-------------------#

# Input file name definitions
fileComps = 'Compartments.txt' # input
fileSpecies = 'Species.txt' # input
fileStoic = 'StoicMat.txt' # input
fileRatelaws = 'Ratelaws.txt' # input
fileParamsOut = 'ParamsAll.txt' # output: Lists all parameter names, rxn names, values

#%% Import required packages
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.getcwd()),'bin'))

import libsbml
import importlib
import amici
import numpy as np
import re
import pandas as pd
import antimony as sb

#%% Define working directory, model name
cd = os.getcwd()
wd = os.path.dirname(cd)
input_path = os.path.join(wd,'input_files')

# Antimony model name and information text
fileModel = open(os.path.join(wd,'SPARCED.txt'),'w') # file name
fileModel.write("# PanCancer Model by Birtwistle Lab \n") # some explanation
fileModel.write("model SPARCED()\n") # model name

# SBML file name
sbml_file = 'SPARCED.xml'
# Name of the model that will also be the name of the python module
model_name = sbml_file[0:-4] 
# Directory to which the generated model code is written
model_output_dir = model_name 
# The AMICI package will create this folder while compiling the model, refer to AMICI github page for more details

#%% Input file processing
# Initializing compartment and volume lists
compartments = []
volumes = []

# Create/write compartments
compartment_sheet = np.array([np.array(line.strip().split("\t")) for line in open(os.path.join(input_path,fileComps))])

#read in each line minus the header row of compartments file
for row in compartment_sheet[1:]:
    compartments.append(row[0])
    volumes.append(row[1])
    
fileModel.write("\n  # Compartments and Species:\n") # Antimony Compartments/Species module title
for idx in range(len(compartments)):
    compName = compartments[idx]
    fileModel.write("  Compartment %s; " % (compName))
fileModel.write("\n")

# Write species and assign compartments
species_sheet = np.array([np.array(line.strip().split("\t")) for line in open(os.path.join(input_path,'Species.txt'), encoding='latin-1')])

#read in each line minus the header row of species file
species_compartments = [] # Create a list of "home" compartments for each species in the model
for row in species_sheet[1:]:
    species_compartments.append(row[1]) 
species_compartments = np.array(species_compartments)

#Write each species to model txt file
fileModel.write("\n")
for idx,val in enumerate(species_sheet[1:]):
    fileModel.write("  Species ")
    fileModel.write("%s in %s" % (val[0], species_compartments[idx]))
    fileModel.write(";\n")
    
# Write reactions
fileModel.write("\n\n  # Reactions:\n") # Antimony Reactions module title

#reads in file from excel and gets rid of first row and column (they're data labels)
stoic_sheet = np.array([np.array(line.strip().split("\t")) for line in open(os.path.join(input_path,'StoicMat.txt'))])

#creates associated ratelaw data list
ratelaw_sheet = np.array([np.array(line.strip().split("\t")) for line in open(os.path.join(input_path,'Ratelaws.txt'))])
ratelaw_data = np.array([line[1:] for line in ratelaw_sheet[1:]])

#gets first column minus blank space at the beginning, adds to stoic data list
stoic_columnnames = stoic_sheet[0]
stoic_rownames = [line[0] for line in stoic_sheet[1:]]
stoic_data = np.array([line[1:] for line in stoic_sheet[1:]])

# builds the important ratelaw+stoic lines into the txt file 
paramnames = []
paramvals = []
paramrxns = []
paramidxs = []
for rowNum, ratelaw in enumerate(ratelaw_data):
    reactants = []
    products = []
    formula="k"+str(rowNum+1)+"*"

    for i, stoic_rowname in enumerate(stoic_rownames):
        stoic_value = int(stoic_data[i][rowNum])
        if stoic_value < 0:
            for j in range(0,stoic_value*-1):
                reactants.append(stoic_rowname)
                formula=formula+stoic_rowname+"*"
        elif stoic_value > 0:
            for j in range(0,stoic_value):
                products.append(stoic_rowname)

    if "k" not in ratelaw[1]:
        # the mass-action formula
        formula=formula[:-1]
        #the parameter
        paramnames.append("k"+str(rowNum+1))
        paramvals.append(np.double(ratelaw[1]))
        paramrxns.append(ratelaw_sheet[rowNum+1][0])
        paramidxs.append(int(0))
    else:
        # specific formula (non-mass-action)
        formula = ratelaw[1]
        j = 1
        params = np.genfromtxt(ratelaw[2:], float) # parameters
        params = params[~np.isnan(params)]
        if len(params) == 1:
            paramnames.append("k"+str(rowNum+1)+"_"+str(j))
            paramvals.append(float(ratelaw[j+1]))
            paramrxns.append(ratelaw_sheet[rowNum+1][0])
            paramidxs.append(int(0))
            pattern = 'k\D*\d*'
            compiled = re.compile(pattern)
            matches = compiled.finditer(formula)
            for ematch in matches:
                formula = formula.replace(ematch.group(),paramnames[-1])
        else:
            for q,p in enumerate(params):
                paramnames.append("k"+str(rowNum+1)+"_"+str(j))
                paramvals.append(float(ratelaw[j+1]))
                paramrxns.append(ratelaw_sheet[rowNum+1][0])
                paramidxs.append(q)
                pattern1 = 'k(\D*)\d*'+'_'+str(j)
                compiled1 = re.compile(pattern1)
                matches1 = compiled1.finditer(formula)
                for ematch in matches1:
                    formula = formula.replace(ematch.group(),paramnames[-1])
                j +=1

    #don't include reactions without products or reactants
    if products == [] and reactants == []:
        pass
    else:
        fileModel.write("  %s: %s => %s; (%s)*%s;\n" % (stoic_columnnames[rowNum], " + ".join(reactants), " + ".join(products), formula, ratelaw[0]))

# Export parameters for each reaction, with corresponding order within the ratelaw and its value
params_all = pd.DataFrame({'value':paramvals,'rxn':paramrxns,'idx':paramidxs},index=paramnames)
params_all.to_csv(os.path.join(wd,fileParamsOut),sep='\t',header=True, index=True)

#%% Set initial conditions for compartments, species and parameters

# Write compartment ICs
fileModel.write("\n  # Compartment initializations:\n")
for idx in range(len(compartments)):
    fileModel.write("  %s = %.6e;\n" % (compartments[idx], np.double(volumes[idx])))
    fileModel.write("  %s has volume;\n" % (compartments[idx]))
    
# Write species ICs
fileModel.write("\n  # Species initializations:\n")
for idx, val in enumerate(species_sheet[1:]):
    fileModel.write("  %s = %.6e;\n" % (val[0],np.double(val[2])))
    
# Write parameter ICs
fileModel.write("\n  # Parameter initializations:\n")
count = 0
for param in paramnames:
    fileModel.write("  %s = %.6e;\n" % (param, np.double(paramvals[count])))
    count += 1

# Write other declarations
constantVars = ['Cytoplasm','Extracellular','Nucleus','Mitochondrion']

fileModel.write("\n  # Other declarations:\n")
fileModel.write("  const")
for constVar in constantVars[:-1]:
    fileModel.write("  %s," % (constVar))
#last item in row needs semicolon
fileModel.write("  %s;\n" % (constantVars[-1]))

# Write unit definitions
fileModel.write("\n  # Unit definitions:")
fileModel.write("\n  unit time_unit = second;")
fileModel.write("\n  unit volume = litre;")
fileModel.write("\n  unit substance = 1e-9 mole;")
fileModel.write("\n  unit nM = 1e-9 mole / litre;")
fileModel.write("\n")

# End the model file
fileModel.write("\nend")
# Close the file
fileModel.close()

#%% Antimony file import and conversion to SBML format

# load model and convert to SBML
if sb.loadFile(os.path.join(wd,"SPARCED.txt")) == 1:
    print("Success loading antimony file")
else:
    print("Failed to load antimony file")
    exit(1)

if sb.writeSBMLFile(os.path.join(wd,"SPARCED.xml"),"SPARCED") == 1:
    print("Success converting antimony to SBML")
else:
    print("Failure converting antimony to SBML")
    exit(1)
    
#%% Annotate SBML

# create interaction components
sbml_reader = libsbml.SBMLReader()
sbml_doc = sbml_reader.readSBML(os.path.join(wd,sbml_file))
sbml_model = sbml_doc.getModel()

# Set species annotations
for idx,row in enumerate(species_sheet[1:]):
    Annot=""
    for col in range(4,(len(row))):
        aa=str(row[col].strip())
        if aa=="nan" or aa == "":
            break
        else:
            Annot=Annot+" "+row[col]
    sbml_model.getSpecies(row[0]).setAnnotation(Annot)
    
# Set compartment annotations
for row in compartment_sheet[1:]:
    sbml_model.getCompartment(row[0]).setAnnotation(row[2])
    
# Write with the same name or use the next section instead of below lines
writer = libsbml.SBMLWriter()
writer.writeSBML(sbml_doc, os.path.join(wd,sbml_file))

#%% Model Compilation

# prepares to use interaction components to synthesize model
sys.path.insert(0, os.path.join(wd,model_output_dir))
model_name = sbml_file[0:-4]
model_output_dir = model_name

sbml_reader = libsbml.SBMLReader()
sbml_doc = sbml_reader.readSBML(os.path.join(wd,sbml_file))
sbml_model = sbml_doc.getModel()

# Create an SbmlImporter instance for our SBML model
sbml_importer = amici.SbmlImporter(os.path.join(wd,sbml_file))

#sets important constants for model build
constantParameters = [params.getId() for params in sbml_model.getListOfParameters()]

# define observables (optional)

ObsMat = pd.read_csv(os.path.join(input_path,'Observables.txt'), sep='\t',header=0, index_col=0)
Vc = float(compartment_sheet[compartment_sheet[:,0]=='Cytoplasm',1])

species_names = np.array([species_sheet[i][0] for i in range(1,len(species_sheet))])
Vol_species = np.array([species_sheet[i][1] for i in range(1,len(species_sheet))])
Vol_species = [float(compartment_sheet[compartment_sheet[:,0]==Vol_species[i],1][0]) for i in range(len(Vol_species))]
Vol_species = pd.Series(Vol_species, index=species_names)

formula_obs = []
for obs in ObsMat.columns:
    sp_obs = ObsMat.index[np.nonzero(np.array(ObsMat.loc[:,obs]>0))[0]]
    sp_obs_id = np.nonzero(np.array(ObsMat.loc[:,obs]>0))[0]
    Vr = Vol_species/Vc
    Vf = Vr*ObsMat.loc[:,obs].values
    if len(sp_obs) == 1:
        formula_i = sp_obs[0]+'*'+str(Vf[sp_obs_id][0])
    elif len(sp_obs) == 2:
        formula_i = str(sp_obs[0]+'*'+str(Vf[sp_obs_id][0])+'+'+sp_obs[1]+'*'+str(Vf[sp_obs_id][1]))
    elif len(sp_obs) > 2:
        formula_i = ''
        for j in range(len(sp_obs)-1):
            formula_i = formula_i+sp_obs[j]+'*'+str(Vf[sp_obs_id][j])+'+'
        formula_i = formula_i+str(sp_obs[-1])+'*'+str(Vf[sp_obs_id][-1])
    formula_obs.append(formula_i)

observables = {}
obs_names = list(ObsMat.columns)
for i in range(len(obs_names)):
    observables[obs_names[i]] = {}
    observables[obs_names[i]]['formula'] = formula_obs[i]


# The actual compilation step

sbml_importer.sbml2amici(model_name,
                          os.path.join(wd,model_output_dir),
                          verbose=False,
                          observables=observables,
                          constantParameters=constantParameters)





