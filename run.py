#!/usr/bin/env python
# encoding: utf-8

"""
 Flask interface for the generation of a metadata file for FTICR.

 *******************************************************************
 * Author: Laura Duciel
 * Copyright (c) 2019
 * CASC4DE
 * Pôle API - 300 Bd Sebastien Brant, 67400 Illkirch Graffenstaden, FRANCE
 *
 * All Rights Reserved
 *
 *******************************************************************

"""
from __future__ import print_function, division, absolute_import
"""


"""
import errno, os, sys, json, glob
op, opd, opb, opj = os.path, os.path.dirname, os.path.basename, os.path.join
import numpy as np
import shutil as sh
import time
import subprocess
import tempfile
import zipfile
from fnmatch import fnmatch
import sys
import io

import urllib.request
urlopen = urllib.request.urlopen

import datetime

from flask import Flask,flash, render_template, request, redirect, url_for, jsonify, send_file,send_from_directory, session
from werkzeug.utils import secure_filename
from sys import platform as _platform
import sys
sys.path.insert(0, "/home/laura/Repositories/spike")
import spike
from spike.File import Solarix, Apex

from scipy.constants import N_A as Avogadro
from scipy.constants import e as electron
from numpy import pi
# Global variables
Debug = False            # Debug Flask
debug = False
PORT = 5005
app = Flask(__name__)
app.secret_key = '8be0cef36ed602cf769e8bf67ec6acf9f4f7093f'

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

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = set(['mscf'])

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET','POST'])
def index():
    '''
    Main page, loads parameter
    '''
    global TMP
    reduced_params={}
    if request.method == 'POST':
        config = request.form.to_dict(flat=False)
        if 'submit' in config:
            del config['submit']
        for element in config:
            config[element] = str(config[element]).strip("[']")
        print(config)
        #config_file = io.open(opj(TMP,'processing_configuration.mscf'), 'w')
        with open(opj(TMP,'metadata.json'), 'w') as outfile:  
            json.dump(config, outfile, indent=2)
        return send_from_directory(directory=TMP, filename="metadata.json",as_attachment=True)
    else:
        if len(os.listdir(app.config['UPLOAD_FOLDER'])) != 0:
            expfold = os.listdir(app.config['UPLOAD_FOLDER'])[0]
            print("***** EXPFOLD is:",expfold,"*****")
    #   configfile = 'processing_example.mscf'
            print("**** reading config file ****")
            param_file = find_param_file(expfold)
            if param_file is not None:
                print('address paramfile is ', param_file)
                params = Apex.read_param(param_file)
                with open(param_file) as f: 
                        lines = f.readlines()
                spectrometer_type = "Apex"
                for l in lines:
                    if "solari" in l:
                        spectrometer_type = "Solarix"
                reduced_params = {}
                reduced_params["name"] = expfold
                reduced_params['SpectrometerType'] = spectrometer_type
                reduced_params['EXC_hi'],reduced_params['EXC_low'],reduced_params['SW_h'], reduced_params['TD'],reduced_params['ML1'], reduced_params['ML2'], reduced_params['ML3'], reduced_params['PULPROG'] = params['EXC_hi'], params['EXC_low'],params['SW_h'], params['TD'],params['ML1'], params['ML2'], params['ML3'], params['PULPROG']
                reduced_params['B0'] = round(float(reduced_params['ML1'])*2*pi/(electron*Avogadro)*1E-3,1)
                if spectrometer_type == "Solarix":
                    print("Solarix!")
                    with open(os.path.join(os.path.dirname(param_file),"ExciteSweep")) as f: 
                        lines = f.readlines()
                    NB_step = len(lines[6:])
                    reduced_params['NBStep'] = NB_step
                    reduced_params['ExciteSweep1st'] = str(lines[6]).strip('\n')
                    reduced_params['ExciteSweepLast'] = str(lines[len(lines)-1]).strip('\n')
                print("Loaded parameters are:", reduced_params)
                return render_template('config_form.html', param=reduced_params)
            else:
                print("PARAM_FILE NONE, using reduced_params.")
                reduced_params["name"] = "Wrong folder imported, no .m found in dataset:"+str(expfold)
                pass
        else:
            print('NO EXPFOLD TRANSMITTED')
            reduced_params["name"] = "No folder imported."
        pre_session = request.form.to_dict(flat=False)
        for element in pre_session:
            pre_session[element] = str(pre_session[element]).strip("[']")
        session = pre_session
        print(pre_session)
        print(session)
        return render_template('config_form.html', param=reduced_params)

def find_param_file(folder):
    global UPLOAD_FOLDER
    F_name = opj(UPLOAD_FOLDER,folder)
    param_file = None
    print("F_name:",F_name)
    for F in os.listdir(F_name):
        print("F:",F)
        if F.endswith('.m'):
            for f in os.listdir(os.path.join(F_name,F)):
                if f.endswith('.method'):
                    param_file = os.path.join(F_name,F,f)
    if param_file == None:
        print("No .m folder in .d folder, check your dataset.")
    print("param_file:", param_file)
    return param_file
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/import_folder', methods=['GET', 'POST'])
def import_folder():
    global UPLOAD_FOLDER
    if request.method == 'POST':
        l = None
        l = os.listdir(app.config['UPLOAD_FOLDER'])
        if l != []:
            print("Content of Upload Folder:",l)
            to_rm = "rm -rf "+str(opj(app.config["UPLOAD_FOLDER"],l[0]))
            print("To RM:",to_rm)
            os.system(to_rm)
        print("Configuration import ...")
        Files = request.files.getlist("file")
        for ff in  Files:
            print('uploading',ff.filename )
            direc, name = op.split(ff.filename)
            os.makedirs(op.join(app.config['UPLOAD_FOLDER'],direc), exist_ok=True)
            ff.save(op.join(app.config['UPLOAD_FOLDER'],ff.filename))
        return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))

def clear(direc):
    if os.path.exists(direc):
        print("Clearing directory:",direc)
        sh.rmtree(direc)

@app.route('/quit')
def shutdown():
    '''
    Shutting down the server.
    '''
    global TMP
    print("Quitting")
    clear(TMP)
    print("Quitting 2")
    sys.exit()

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
