#!/usr/bin/env python
# encoding: utf-8

"""
 Flask interface for the generation of a metadata file for FTICR.

 *******************************************************************
 * Authors: Laura Duciel - Marc-André Delsuc
 * Copyright (c) 2020
 * CASC4DE
 * Pôle API - 300 Bd Sebastien Brant, 67400 Illkirch Graffenstaden, FRANCE
 *
 * All Rights Reserved
 *
 *******************************************************************

"""
from __future__ import print_function, division, absolute_import

import sys, io, socket, urllib.request, re, zipfile, tempfile, subprocess, time, errno, os, json, glob,psutil,calendar
urlopen = urllib.request.urlopen
from flask import render_template, flash, redirect, url_for, request, send_from_directory
op, opd, opb, opj = os.path, os.path.dirname, os.path.basename, os.path.join
from datetime import datetime
from dateutil.relativedelta import *
import shutil as sh
import urllib.request
urlopen = urllib.request.urlopen
import numpy as np
from numpy import pi
from sys import platform as _platform
from fnmatch import fnmatch
from scipy.constants import N_A as Avogadro
from scipy.constants import e as electron
from dateutil.parser import parse
from werkzeug.urls import url_parse
from pathlib import Path
import flask
from flask import Flask,flash, render_template, request, redirect, url_for, jsonify, send_file,send_from_directory, session
from werkzeug.utils import secure_filename

import spike
from spike.File import Solarix, Apex

flaskversion = [int(i) for i in flask.__version__.split(".")]
print("Version of Flask Library:", flaskversion)

# Global variables
Debug = False            # Debug Flask
debug = False
PORT = 5005
app = Flask(__name__)
app.secret_key = 'thisisasecret'

def init():
    "prgm initialisation"
    global  Debug, TMP
    print("Starting Flask Form for FTICR MS Metadata File generation.")
    print("current directory: ", os.path.realpath(os.getcwd()))

    DATA_DICT = {}

    if Debug:
        TMP = op.realpath('./_test')
    else:
        TMP = tempfile.mkdtemp()
        print('TMP: ',TMP)

init()

UPLOAD_FOLDER = opj(TMP,'imports')
user_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER,'Metadata_Upload_Folder') #os.path.join(working_dir,'Metadata_Upload_Folder')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
@app.route('/index')
def index():
    return redirect(url_for('create_metadata'))

def clear(direc):
    if os.path.exists(direc):
        print("Clearing directory:",direc)
        sh.rmtree(direc)

def find_param_file(ExpName):
    """
    Used to find a parameter file within an experiment folder from expname (name of the folder)
    return the kind of of parameter file (metadata or bruker) and the path to the file
    """
    param_file_type = None
    BaseExpName = ExpName.strip('.')[:-2] 
    print("BaseExpName:",BaseExpName)
    working_dir=os.getcwd()
    print("working dir:",working_dir) 
    #user_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER,'Metadata_Upload_Folder') #os.path.join(working_dir,'Metadata_Upload_Folder')
    if not os.path.exists(user_UPLOAD_FOLDER):
        os.makedirs(user_UPLOAD_FOLDER)
    param_file = None
    project_dir = os.path.join(user_UPLOAD_FOLDER,os.listdir(user_UPLOAD_FOLDER)[0])
    if "{0}_v0.meta".format(BaseExpName) in os.listdir(project_dir):
        print("There is a meta file!")
        param_file = os.path.join(project_dir,"{0}_v0.meta".format(BaseExpName))
        param_file_type = "meta_file"
    else: #look for .d
        F = os.path.join(project_dir,"{0}.d".format(BaseExpName))
        for f in os.listdir(os.path.join(project_dir,F)):
            if f.endswith('.m'):
                for ff in os.listdir(os.path.join(project_dir,F,f)):
                    if ff.endswith('.method'):
                        param_file = os.path.join(project_dir,F,f,ff)
                        param_file_type = "brukermethod_file"
    if param_file == None:
        print("No .m folder in .d folder, check your dataset.")
    print("param_file:", param_file)
    return param_file_type,param_file

@app.route('/import_folder', methods=['GET', 'POST'])
def import_folder():
    """
    Used to import project folder into what is called "Metadata_Upload_Folder" and which is used as a base directory to find experiments.
    """
    working_dir=os.getcwd()
    print("working dir:",working_dir) 
    #user_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER,'Metadata_Upload_Folder') #os.path.join(working_dir,'Metadata_Upload_Folder')
    if not os.path.exists(user_UPLOAD_FOLDER):
        os.makedirs(user_UPLOAD_FOLDER)
    if request.method == 'POST':
        l = None
        l = os.listdir(user_UPLOAD_FOLDER)
        if l != []:
            print("Content of Upload Folder:",l)
            to_rm = str(opj(user_UPLOAD_FOLDER,l[0]))
            print("To RM:",to_rm) 
            clear(to_rm) #The folder is emptied before uploading new project folder
        print("Configuration import ...")
        Files = request.files.getlist("file")
        for ff in  Files:
            print('uploading',ff.filename )
            direc, name = op.split(ff.filename)
            os.makedirs(op.join(user_UPLOAD_FOLDER,direc), exist_ok=True)
            ff.save(op.join(user_UPLOAD_FOLDER,ff.filename))
        return redirect(url_for('create_metadata'))
    else:
        return redirect(url_for('create_metadata'))

@app.route('/select_experiment', methods=['GET', 'POST'])
def select_experiment():
    ExpName=None
    working_dir=os.getcwd()
    #user_UPLOAD_FOLDER = os.path.join(working_dir,'Metadata_Upload_Folder')
    project_dir = os.path.join(user_UPLOAD_FOLDER,os.listdir(user_UPLOAD_FOLDER)[0])
    if request.method == 'POST':
        ExpIndex = request.form['ExpList']
        print("ExpIndex",ExpIndex)
        ExpList = []
        for F in os.listdir(project_dir):
            if F.endswith('.d'):
                print("There is a .d folder!")
                ExpList.append((F))
        ExpName = ExpList[int(ExpIndex)]
        print("ExpName selected:", ExpName)
        return redirect(url_for('create_metadata', ExpName=ExpName))
    else:
        return redirect(url_for('create_metadata'))

def generate_base_dico(param_file):
    """
    reads a *.d Bruker FTICR dataset and generate a dictionary
    """
    print("*** Generating base dico ***")
    # read all params
    print("*** Param file is:",param_file,"***")
    params = Apex.read_param(str(param_file))
    # determine file type
    with open(param_file) as f: 
            lines = f.readlines()
    #print(lines)
    SpectrometerType = "Apex"
    for l in lines:
        if "solari" in l:
            SpectrometerType = "Solarix"

    # build meta data
    reduced_params = {}
    reduced_params['MetaFileType'] = "EUFTICRMS v 1.0"
    reduced_params['MetaFileVersion'] = "1.0.0"
    reduced_params['MetaFileCreationDate'] = datetime.now().isoformat()

    reduced_params['FileName'] = str(Path(param_file)).split(os.sep)[-3].strip('.d')
    print("NAME*****",Path(param_file))
    print("****----****",str(Path(param_file)).split(os.sep))
    reduced_params['SpectrometerType'] = SpectrometerType
    AcquisitionDate = parse(params['CLDATE'])
    reduced_params['AcqDate'] = AcquisitionDate.strftime('%Y-%m-%d')
    reduced_params['EndEmbargo'] = (AcquisitionDate + relativedelta(months=18)).strftime('%Y-%m-%d')

    reduced_params['ExcHighMass'] = params['EXC_hi']
    reduced_params['ExcLowMass'] = params['EXC_low']
    reduced_params['SpectralWidth'] = params['SW_h']
    reduced_params['AcqSize'] =  params['TD']
    reduced_params['CalibrationA'] = params['ML1']
    reduced_params['CalibrationB'] = params['ML2']
    reduced_params['CalibrationC'] = params['ML3']
    reduced_params['PulseProgam'] = params['PULPROG']

    reduced_params['MagneticB0'] = str(round(float(params['ML1'])*2*np.pi/(electron*Avogadro)*1E-3,1))
    if SpectrometerType == "Solarix":
        excfile = Path(param_file).parent/"ExciteSweep"
        print(excfile)
        if excfile.exists():
            with open(excfile,'r') as f: 
                lines = f.readlines()
            NB_step = len(lines[6:])
            reduced_params['ExcNumberSteps'] = str(NB_step)
            reduced_params['ExcSweepFirst'] = str(lines[6]).strip('\n')
            reduced_params['ExcSweepLast'] = str(lines[len(lines)-1]).strip('\n')
        else:
            reduced_params['ExcNumberSteps'] = "NotDetermined"
            reduced_params['ExcSweepFirst'] = "NotDetermined"
            reduced_params['ExcSweepLast'] = "NotDetermined"
    print("Loaded parameters are:", reduced_params)
    return reduced_params

def generate_reduced_params(param_file, param_file_type, expfold):
    reduced_params={}
    print("*** Generating reduced params ***")
    if param_file is not None and param_file_type=="brukermethod_file":
        print('address paramfile is ', param_file)
        reduced_params = generate_base_dico(param_file)
    elif param_file is not None and param_file_type=="meta_file":
        with open(param_file) as f:
            reduced_params = json.load(f)
        reduced_params['MetaFileEditionDate'] = datetime.now().isoformat()
    else:
        print("PARAM_FILE NONE, using reduced_params.")
        reduced_params["fold_name"] = "Wrong folder imported, no .m found in dataset:"+str(expfold)
        pass
    return reduced_params


@app.route('/create_metadata/',defaults={'ExpName': None}, methods=['GET','POST'])
@app.route('/create_metadata/<ExpName>', methods=['GET','POST'])
def create_metadata(ExpName):
    '''
    Metadata form, working in current dir
    '''
    global TMP
    ExpList = []
    reduced_params={}
    working_dir=os.getcwd()
    #user_UPLOAD_FOLDER = os.path.join(working_dir,'Metadata_Upload_Folder')
    if not os.path.exists(user_UPLOAD_FOLDER):
        os.makedirs(user_UPLOAD_FOLDER)
    if len(os.listdir(user_UPLOAD_FOLDER)) != 0:
        project_dir = os.path.join(user_UPLOAD_FOLDER,os.listdir(user_UPLOAD_FOLDER)[0])
        i = 0
        for F in os.listdir(project_dir):
                if F.endswith('.d'):
                    print("There is a .d folder!")
                    ExpList.append((i,F))
                    i+=1
    print("ExpName:", ExpName)
    # print("ExpList: ",ExpList)
    if ExpName is None and ExpList!=[]:
        ExpName = ExpList[0][1]
        print("Using default ExpName:", ExpName)
    if len(os.listdir(user_UPLOAD_FOLDER)) != 0 and ExpName is not None:
        print("***** Project Dir is:",project_dir,"*****")
        try:
            param_file_type, param_file = find_param_file(ExpName)
            print("param_file_type,param_file",param_file_type,param_file)
            reduced_params = generate_reduced_params(param_file,param_file_type,project_dir)
            reduced_params['ExpName'] = ExpName
            print('fold_name:',project_dir.split('/')[-1])
            reduced_params['fold_name'] = project_dir.split('/')[-1]
        except:
            print('NO EXPFOLD TRANSMITTED - Wrong format imported')
            reduced_params["fold_name"] = "The format of the imported folder was not correct, please see the documentation above to get a structure example."
            reduced_params["ExpName"] = "No experiment can be loaded, please import a correct folder."
    else:
        print('NO EXPFOLD TRANSMITTED - No folder imported')
        reduced_params["fold_name"] = "No folder imported."
        reduced_params["ExpName"] = "No experiment"
    if request.method == 'POST':
        config = request.form.to_dict(flat=False)
        config['Comment'] = '{}'.format(request.form['Comment'])
        config['RawPreprocess'] = '{}'.format(request.form['RawPreprocess'])
        if 'submit' in config:
            del config['submit']
        for element in config:
            config[element] = str(config[element]).strip("[']")
        meta_json = reduced_params.copy()
        meta_json.update(config)
        if 'ExpList' in meta_json:
            del meta_json['ExpList']
        if param_file_type=="meta_file":
            Fname = param_file.split("/")[-1]
            meta_version = Fname.strip('.meta').split("_")[-1]
            list_base_filename = Fname.strip('.meta').split("_")
            list_base_filename = list_base_filename[:-1]
            base_filename = "_".join(list_base_filename)
            filename = '{0}_v{1}.meta'.format(base_filename, str(int(meta_version.strip('v'))+1))
        else:
            F = os.listdir(user_UPLOAD_FOLDER)[0]
            print("FoldName:",os.path.splitext(F)[0])
            filename = '{0}_v0.meta'.format(ExpName.strip('.')[:-2])
        with open(opj(user_UPLOAD_FOLDER,os.listdir(user_UPLOAD_FOLDER)[0],filename), 'w') as outfile:  
            json.dump(meta_json, outfile, indent=2)
        if flaskversion[0] == 1:
            return send_from_directory(directory=opj(user_UPLOAD_FOLDER,os.listdir(user_UPLOAD_FOLDER)[0]), filename=filename, as_attachment=True)
        elif flaskversion[0] == 2: #change for compatibility with flask v2.0 and higher
                return send_from_directory(directory=opj(user_UPLOAD_FOLDER,os.listdir(user_UPLOAD_FOLDER)[0]), path=filename, as_attachment=True)
    else:
        return render_template('create_metadata.html', param=reduced_params, ExpList=ExpList)

@app.route('/quit')
def shutdown():
    '''
    Shutting down the server.
    '''
    global TMP
    print("Quitting")
    clear(TMP)
    return redirect(url_for('closing'))
    print("Quitting 2")
    sys.exit()

@app.route('/closing')
def closing():
    return render_template('close_tab.html')

def main(startweb=True):
    import threading, webbrowser
    # init()
    port = PORT
    expfold = ""
    url = "http://127.0.0.1:{0}/{1}".format(port,expfold) # 127.0.0.1
    if startweb:
        if _platform == "linux" or _platform == "linux2":
            platf = 'lin'
        elif _platform == "darwin":
            platf = 'mac'
        elif _platform == "win32":
            platf = 'win'

        print ("platf",platf)
        # MacOS
        if platf == 'mac':
            chrome_path = 'open -a /Applications/Google\\ Chrome.app %s'
        # Linux
        if platf == 'lin':
            chrome_path = '/usr/bin/google-chrome %s'
        if platf != 'win':
            b = webbrowser.get(chrome_path)
            threading.Timer(1.25, lambda: b.open_new(url)).start() # open a page in the browser.
        else:
            webbrowser.open(url, new=0, autoraise=True)
            # subprocess.Popen('"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" {0}'.format(url))
    print( """
    ***************************************************************
    Launching the Flask Form for FTICR Metadata

    If the Chrome browser does not show up or is not available,
    open your favorite browser and go to the following addess:

    {0}

    """.format(url) )
    try:
        app.run(port = port , host='127.0.0.1', debug = Debug) # port
    except OSError:
        print("################################################################################")
        print("             WARNING\n")
        print("The program could not be started, this could be related to a PORT already in use")
        print("Please change the port number in the configuration file and retry.\n")
        print("################################################################################")


if __name__ == '__main__':
    main()
